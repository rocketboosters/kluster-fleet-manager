import datetime
import typing

from kuber.latest import core_v1

from manager import _configs
from manager import _controller
from manager import _types


def _describe_external_instances(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
    cluster_fleet_nodes: typing.Dict[str, "_types.FleetNode"],
) -> typing.List[dict]:
    """
    List EC2 instance descriptions for any nodes in the fleet but not in the cluster.

    These could be instances warming up or shutting down, but could also be instances
    that are not healthy and weren't able to connect as a worker node to the cluster.
    If no external instances are found this will be an empty list.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet:
        The EC2 fleet in which to query for instances.
    :param cluster_fleet_nodes:
        Fleet nodes that are currently in the cluster and should be ignored.
    """
    client = configs.session.client("ec2")
    response = client.describe_fleet_instances(FleetId=fleet.identifier)
    fleet_instance_ids = [f.instance_id for f in cluster_fleet_nodes.values()]
    external_instance_ids = [
        instance["InstanceId"]
        for instance in (response.get("ActiveInstances") or [])
        if instance["InstanceId"] not in fleet_instance_ids
    ]

    if not external_instance_ids:
        return []

    response = client.describe_instances(InstanceIds=external_instance_ids)
    return [
        instance
        for reserve in (response.get("Reservations") or [])
        for instance in (reserve.get("Instances") or [])
    ]


def get_external_nodes(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
    cluster_fleet_nodes: typing.Dict[str, "_types.FleetNode"],
) -> typing.Dict[str, "_types.FleetNode"]:
    """
    Retrieve fleet nodes that are not currently part of the cluster.

    These could be nodes warming up, or shutting down. But they could also be
    unhealthy nodes that never connected to the cluster. By including them
    in the nodes, we can manage their lifecycle as well and avoid issues
    with them persisting in the dark while they're disassociated with the
    cluster.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet:
        The EC2 fleet in which to query for instances.
    :param cluster_fleet_nodes:
        Fleet nodes that are currently in the cluster and should be ignored.
    """
    instances = _describe_external_instances(configs, fleet, cluster_fleet_nodes)
    external_instances = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    for instance in instances:
        created_at = instance.get("LaunchTime") or now
        age = int(max(0.0, (now - created_at).total_seconds()))
        name = instance["PrivateDnsName"]
        external_instances[name] = _types.FleetNode(
            name=name,
            seconds_old=age,
            instance_id=instance.get("InstanceId") or "unknown-instance-id",
            requirements=fleet.requirements,
            is_unblocked=age > 300,
            state=(
                _configs.WARMING_UP_STATE
                if name or age < 20
                else _configs.SHUTTING_DOWN_STATE
            ),
            resource=None,
            pods={},
        )

    return external_instances


def get_nodes(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
) -> typing.Dict[str, "_types.FleetNode"]:
    """
    Create a list of FleetNode objects for each node in the cluster in the fleet.

    The FleetNode objects contain the node resource objects themselves, along with some
    high-level construct properties that make it easier to filter and map node
    behaviors elsewhere.
    """
    grace_period = configs.get_inactive_grace_period()
    now = datetime.datetime.utcnow()
    api = core_v1.Node.get_resource_api()
    pod_capacities = _controller.get_pods(configs, grace_period)

    nodes = {}
    for node_data in api.list_node().items:
        node = core_v1.Node().from_dict(node_data.to_dict())
        if node.metadata.labels.get("fleet") != fleet.name:
            continue

        name = node.metadata.name
        created_at = datetime.datetime.fromisoformat(
            node.metadata.creation_timestamp.replace("Z", "").replace("+00:00", "")
        )
        age = (now - created_at).total_seconds()
        state = node.metadata.labels.get(_configs.STATE_KEY)
        requirements = fleet.requirements
        pods = {p.pod_id: p for p in pod_capacities if p.pod.spec.node_name == name}
        is_unblocked = requirements is not None and not pods and age > grace_period

        nodes[name] = _types.FleetNode(
            name=name,
            instance_id=node.spec.provider_id.rsplit("/", 1)[-1],
            seconds_old=age,
            is_unblocked=is_unblocked,
            state=state or _configs.ACTIVE_STATE,
            resource=node,
            requirements=requirements,
            pods=pods,
        )

    return {**nodes, **get_external_nodes(configs, fleet, nodes)}
