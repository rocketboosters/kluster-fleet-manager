import typing

from kuber.latest import core_v1

from manager import _configs
from manager import _controller
from manager import _types


def _get_unblocked_nodes(
    fleet_nodes: typing.List["_types.FleetNode"],
) -> typing.Dict[str, "_types.FleetNode"]:
    """
    Get a dictionary containing nodes that are in a an unblocked state.

    This means they have no active pods or pending pod resource requests, but
    the node does have a resource (meaning that it is actively part of the
    kubernetes cluster). The keys of the returned dictionary are the node
    identifiers, which will be the kubernetes names for the nodes if such a
    name has been assigned or the AWS EC2 instance ID if no kubernetes name
    has been assigned yet.

    :param fleet_nodes:
        Node definitions for all nodes currently in the specified fleet.
    """
    all_nodes = {(n.name or n.instance_id): n for n in fleet_nodes}
    return {ident: n for ident, n in all_nodes.items() if n.is_unblocked and n.resource}


def _get_blocked_nodes(
    fleet_nodes: typing.List["_types.FleetNode"],
) -> typing.Dict[str, "_types.FleetNode"]:
    """
    Get a dictionary containing nodes that are in a blocked state.

    This means they have active pods or pending pod resource requests on them.
    The keys of the returned dictionary are the node identifiers, which will
    be the kubernetes names for the nodes if such a name has been assigned
    or the AWS EC2 instance ID if no kubernetes name has been assigned yet.

    :param fleet_nodes:
        Node definitions for all nodes currently in the specified fleet.
    """
    all_nodes = {(n.name or n.instance_id): n for n in fleet_nodes}
    unblocked_nodes = _get_unblocked_nodes(fleet_nodes)
    return {ident: n for ident, n in all_nodes.items() if ident not in unblocked_nodes}


def _get_bouncable_nodes(
    fleet_nodes: typing.List["_types.FleetNode"],
) -> typing.Dict[str, "_types.FleetNode"]:
    """
    Get a dictionary containing nodes that are in a bouncable state.

    This means they have active pods, but those pods could be restarted on
    another node. The keys of the returned dictionary are the node identifiers,
    which will be the kubernetes names for the nodes if such a name has been
    assigned or the AWS EC2 instance ID if no kubernetes name has been
    assigned yet.

    :param fleet_nodes:
        Node definitions for all nodes currently in the specified fleet.
    """
    return {
        ident: n
        for ident, n in _get_blocked_nodes(fleet_nodes).items()
        if n.resource
        and n.is_retirable
        and all([p.is_bouncable for p in (n.pods or {}).values()])
    }


def _get_nodes_to_terminate(
    requirements: "_types.FleetRequirements",
    fleet_nodes: typing.List["_types.FleetNode"],
    reduce_by: int,
) -> typing.List["_types.FleetNode"]:
    """
    Find any of the specified fleet nodes list that can and should be terminated.

    A node can be terminated if it is not blocked by a pod or if all of the blocking
    pods on a node are in a bouncable state (i.e. they are part of a deployment and
    can be rescheduled elsewhere without major interruption).

    :param requirements:
        Configuration of the fleet in which the fleet nodes exist.
    :param fleet_nodes:
        Node definitions for all nodes currently in the specified fleet.
    :param reduce_by:
        The number of nodes that are no longer needed needed to meet the
        current capacity requirements of the specified fleet.
    """
    unblocked_nodes = _get_unblocked_nodes(fleet_nodes)
    if not requirements.bounce_deployment_pods:
        return list(unblocked_nodes.values())[:reduce_by]

    bouncable_nodes = list(
        sorted(
            _get_bouncable_nodes(fleet_nodes).values(),
            key=lambda n: len(n.pods or {}),
        )
    )
    return (list(unblocked_nodes.values()) + bouncable_nodes)[:reduce_by]


def prepare_nodes_for_termination(
    configs: "_types.ManagerConfigs",
    target_capacity: int,
    fleet: "_types.Fleet",
):
    """
    Taint unneeded nodes as "no schedule".

    This will prevent new pods from being scheduled with the node. Once they have no
    blocking pods they will be tainted as no execute as well, which will evict any
    non-blocking pods gracefully from the node before it is finally
    terminated. For nodes that remain blocked after initial no schedule
    tainting, they are given a grace period of ``COUNT_VALUE`` loops before
    they are forcibly tainted as no execute and so ready for

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param target_capacity:
        The targeted capacity for the fleet.
    :param fleet:
        Requirements that define the fleet on which to carry out the
        termination operation.
    """
    fleet_nodes = list(_controller.get_nodes(configs, fleet).values())
    reduce_by = max(0, len(fleet_nodes) - target_capacity)

    no_schedule = core_v1.Taint(
        effect="NoSchedule", key=_configs.STATE_KEY, value=_configs.TERMINATING_STATE
    )

    no_execute = core_v1.Taint(
        effect="NoExecute", key=_configs.STATE_KEY, value=_configs.TERMINATING_STATE
    )

    requirements = fleet.requirements
    nodes_to_terminate = _get_nodes_to_terminate(
        requirements=requirements,
        fleet_nodes=fleet_nodes,
        reduce_by=reduce_by,
    )

    tainted_for_termination: typing.List[_types.FleetNode] = []
    for node in nodes_to_terminate:
        if node.resource is None:
            continue

        current_state = node.resource.metadata.labels.get(
            _configs.STATE_KEY, _configs.ACTIVE_STATE
        )

        if current_state == _configs.TERMINATING_STATE:
            # Skip nodes that are already tainted for termination.
            continue

        taints = [no_schedule, no_execute]
        state = _configs.TERMINATING_STATE

        node_patch = core_v1.Node()
        node_patch.metadata.labels[_configs.STATE_KEY] = state
        node_patch.metadata.name = node.name
        node_patch.spec.taints = taints
        node_patch.patch_resource()

        tainted_for_termination.append(node)

    if tainted_for_termination:
        configs.log(
            message="tainted_nodes_for_termination",
            data={
                "state": _configs.TERMINATING_STATE,
                "taints": [no_schedule.effect, no_execute.effect],
                "nodes": {
                    n.name: {
                        "id": n.instance_id,
                        "seconds_old": n.seconds_old,
                        "fleet": n.requirements.name if n.requirements else None,
                    }
                    for n in tainted_for_termination
                },
            },
        )


def terminate_nodes(configs: "_types.ManagerConfigs", fleet: "_types.Fleet"):
    """
    Terminate nodes to reduce the fleet to the specified target capacity.

    This function is idempotent as it relies on labeling and tainting nodes during the
    termination process to prevent overaggressive termination behaviors. This function
    will do nothing if the target capacity is already achievable with the current state
    of termination within the cluster.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet:
        Fleet object that defines which fleet to be operating upon.
    :return:
        A list of node objects that are now undergoing the garbage
        collection termination process.
    """
    nodes_to_terminate = [
        n
        for n in _controller.get_nodes(configs, fleet).values()
        if n.state == _configs.TERMINATING_STATE
        or (n.state == _configs.WARMING_UP_STATE and n.is_unblocked)
        or n.state == _configs.SHUTTING_DOWN_STATE
    ]

    if not nodes_to_terminate:
        # Abort if there are no nodes available for garbage collection at
        # the moment.
        return []

    client = configs.session.client("ec2")
    client.terminate_instances(InstanceIds=[n.instance_id for n in nodes_to_terminate])

    configs.log(
        "terminating_nodes",
        {
            "action": "terminating_nodes",
            "fleet": fleet.name,
            "nodes": {node.name: node.instance_id for node in nodes_to_terminate},
        },
    )

    return nodes_to_terminate


def shrink_fleet(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
    target_capacity: int,
) -> typing.List[core_v1.Node]:
    """
    Reduce the size of the specified fleet to the given target capacity.

    This is done by first adjusting the capacity of the fleet and then terminating any
    unneeded nodes if any are available to be garbage collected. The fleets have been
    set up so that they will not delete nodes themselves if the capacity is reduced,
    which allows for a more graceful deletion process based on Kubernetes allocation
    carried out explicitly here.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param target_capacity:
        The number of nodes to target in this fleet.
    :param fleet:
        Ec2 fleet object that defines the fleet on which to operate.
    :return:
        A list of nodes being garbage collected as part of this scale down
        action or an empty list if none were available for termination.
    """
    if fleet.capacity > target_capacity:
        success = _controller.adjust_fleet(configs, fleet, target_capacity)
        if not success:
            # Skip node termination if adjusting the fleet capacity was not
            # successful. Don't want the reduction process to be fighting the
            # fleet as it tries to maintain capacity.
            print(f"Failed to shrink {fleet.name} capacity.")
            return []

    # Terminate any nodes that are already set to be terminated. EC2 fleet
    # nodes do not terminate automatically when fleet capacity is changed
    # because we have configured them not to. This allows us to shrink fleets
    # gracefully in Kubernetes by first tainting them to evict pods before
    # shutting them down. It also allows us to more intelligently kill nodes
    # instead of the EC2 fleet randomly removing nodes on us.
    terminated = terminate_nodes(configs, fleet)

    # Update existing nodes with termination taints as needed so they will
    # be ready for the next contraction cycle.
    prepare_nodes_for_termination(configs, target_capacity, fleet)

    return terminated
