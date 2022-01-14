import math
import typing

from manager import _controller
from manager import _types


def _is_suitable(
    item: "_types.CapacityItem",
    fleet: "_types.FleetRequirements",
    nodes: typing.Dict[str, "_types.FleetNode"],
) -> bool:
    """
    Determine whether a pod is suitable for being run in the specified fleet.

    :param item:
        Pod capacity item to determine the capacity of.
    :param fleet:
        Fleet requirements description that is used to determine the capacity
        and eligibility of each capacity item within the identified fleet.
    :param nodes:
        Current fleet nodes that will be used to determine which pods are
        already scheduled on in fleets.
    """
    node = nodes.get(item.pod.spec.node_name)
    in_sector = fleet.sector == item.sector
    in_fleet = item.size in [None, fleet.size]
    will_fit = item.memory < fleet.memory_max and item.cpu < fleet.cpu_max
    no_smaller = item.memory >= fleet.memory_min or item.cpu >= fleet.cpu_min
    running_in_fleet = node is not None and node.requirements == fleet
    only_this_fleet = item.size == fleet.size

    return running_in_fleet or (
        node is None
        and in_fleet
        and in_sector
        and will_fit
        # Prevent it from being selected by a larger-than-necessary
        # fleet unless this fleet has been explicitly set on the PodSpec's
        # nodeSelector.
        and (no_smaller or only_this_fleet)
    )


def _compute_fleet_capacity(
    fleet: "_types.FleetRequirements",
    members: typing.Dict["_types.CapacityItem", float],
) -> float:
    """
    Determine overall capacity requirement for the fleet.

    This is specified as a fractional number of nodes required to schedule all members
    in this fleet. To determine the actual node count the ceiling of this returned
    value should be used. This function uses an approximate bin-packing algorithm to
    pack pods into nodes based on capacities. It's not a perfect solution to the
    bin-packing problem but outperforms a first-forward packing approach while
    remaining a relatively simple implementation.

    :param fleet:
        Fleet requirements description for which to determine the capacity.
    :param members:
        A dictionary of capacity items and resource capacities for all
        items allocated to the specified fleet. The capacity items are
        the returned keys and the values are a float that represents the amount
        of capacity needed by that pod to be schedulable in the given fleet.
    :return:
        Fractional number of nodes of capacity required for this fleet.
    """
    capacities = [c for item, c in members.items() if item.needs_resources]
    pod_count = len(capacities)
    nodes: typing.List[float] = [0.0 for _ in range(pod_count)]
    for value in sorted(capacities, reverse=True):
        index = next(i for i in range(pod_count) if (nodes[i] + value) <= 1)
        nodes[index] += value
    return max(fleet.capacity_min, sum([1 for b in nodes if b > 0]))


def allocate(
    fleet: "_types.FleetRequirements",
    capacities: typing.List["_types.CapacityItem"],
    nodes: typing.Dict[str, "_types.FleetNode"],
) -> typing.Dict["_types.CapacityItem", float]:
    """
    Create a dictionary of capacity items and resource values for the fleet.

    This contains all items that will fit within the specified fleet. The capacity
    items are the returned keys and the values are a float that represents the amount
    of capacity needed by that pod to be schedulable in the given fleet. If
    the pod resources are too small or large for the given fleet they will be
    left out of the returned results.

    :param capacities:
        List of capacities to consider allocating to the capacity of the fleet.
    :param fleet:
        Fleet requirements description that is used to determine the capacity
        and eligibility of each capacity item within the identified fleet.
    :param nodes:
        Current fleet nodes that will be used to determine which pods are
        already scheduled on in fleets.
    """
    return {
        # The min here ensures that a suitable pod never allocates more
        # resources than a node provides. It would seem like this would never
        # happen, but it can happen when the over subscription is taken into
        # account. If the control plane schedules a pod in a fleet where it
        # fits without over subscription, this value can actually be greater
        # than 1 without clamping it to 1.
        c: min(1.0, max(c.cpu / fleet.cpu_max, c.memory / fleet.memory_max))
        for c in capacities
        if _is_suitable(c, fleet, nodes)
    }


def repack(
    fleet: "_types.FleetRequirements",
    members: typing.Dict["_types.CapacityItem", float],
    memberships: typing.Dict[
        "_types.FleetRequirements", typing.Dict["_types.CapacityItem", float]
    ],
):
    """
    Optimize fleet allocation to utilize fewer, larger nodes when available.

    Allocation of fleets individually can lead to overcapacity because excess
    capacity may exist in larger fleets in the same sector that could include
    members of another fleet. This function will attempt to repack the members
    of the specified fleet into other fleets where possible to reduce wasted
    capacity.

    :param fleet:
        Fleet to be repacked into other fleets in the same sector if possible.
    :param members:
        Members of the specified fleet to potentially be repacked elsewhere.
        This dictionary will be mutated in the function if members are moved
        into other fleets.
    :param memberships:
        Memberships of all fleets to iterate over and potentially repack
        members of the specified fleet into.
    :return:
        Nothing is returned here, the memberships are mutated within the
        the function.
    """
    for other_fleet, other_members in memberships.items():
        is_packable = (
            other_fleet != fleet
            and other_fleet.sector == fleet.sector
            and other_fleet.capacity_weight > fleet.capacity_weight
        )
        if is_packable:
            _pack_into(fleet, members, other_fleet, other_members)


def _pack_into(
    from_fleet: "_types.FleetRequirements",
    from_members: typing.Dict["_types.CapacityItem", float],
    to_fleet: "_types.FleetRequirements",
    to_members: typing.Dict["_types.CapacityItem", float],
):
    """
    Try to pack members in ``from_members``  into the ``to_members`` fleet.

    This will repack only if there is excess capacity in the ``to_fleet`` that
    can be filled by members in the ``from_fleet`` without changing the total
    whole capacity of the ``from_fleet``. For example, if the raw capacity of
    the ``to_fleet`` is currently 2.3, which will generate a desired total
    capacity of 3 (because nodes are whole numbers), members of the
    ``from_fleet`` could be added to use that extra 0.7 capacity.

    :param from_fleet:
        Requirements for the fleet from which members may be removed and
        placed in the corresponding ``to_fleet``. The requirements of this
        fleet should be smaller than the ``to_fleet`` or obviously none of the
        members will fit.
    :param from_members:
        Current allocated capacity membership in the ``from_fleet``. This
        will potentially be mutated within the function as members are removed
        from this dictionary and added to the ``to_members`` dictionary
        instead.
    :param to_fleet:
        Requirements for the fleet to which members may be added if this
        fleet has excess capacity to be allocated.
    :param to_members:
        Current allocated capacity membership in the ``from_fleet``. This
        will potentially be mutated within the function as members are added
        to this dictionary and removed from the ``from_members`` dictionary.
    :return:
        Nothing is returned here, the memberships are mutated within the
        the function.
    """
    to_raw = sum(to_members.values())
    to_desired = math.ceil(to_raw)
    if (to_desired - to_raw) <= 0.05:
        return

    # Scale down the smaller items to the utilization of the larger one.
    scale = to_fleet.capacity_weight / from_fleet.capacity_weight
    shrunk = [
        (capacity / scale, item)
        for item, capacity in from_members.items()
        if not item.size and item.pod.spec.node_name is None
    ]
    shrunk.sort(key=lambda x: x[0])

    for capacity, item in shrunk:
        new_capacity = sum(to_members.values()) + capacity

        if new_capacity >= (to_desired - 0.05):
            # If this pod won't pack then none of the others will either
            # and it's time to stop packing.
            break

        to_members[item] = capacity
        del from_members[item]


def _create_fleet_allocation(
    fleet: "_types.FleetRequirements",
    members: typing.Dict["_types.CapacityItem", float],
) -> typing.Dict[str, typing.Any]:
    """
    Create an allocation configuration for the given fleet and its capacity members.

    :param fleet:
        Requirements of the fleet to be echoed to the display.
    :param members:
        Capacity pod members for the specified fleet.
    """
    pod_capacities = {
        # Zero out resource allocations for pods that do not need resources. Pods that
        # do not need resources are ones that should still linger on the node because
        # of grace period settings, but are completed and do not need to utilize
        # node resources while they linger.
        item.pod_id: capacity if item.needs_resources else 0
        for item, capacity in members.items()
    }
    raw = max(fleet.capacity_min, math.ceil(sum(pod_capacities.values())))
    computed = _compute_fleet_capacity(fleet, members)
    target = int(math.ceil(computed))
    return {
        "is_empty": raw == 0 and computed == 0,
        "fleet": fleet.name,
        "capacity": {
            "raw": raw,
            "computed": computed,
            "target": int(math.ceil(target)),
        },
        "pod_capacities": pod_capacities,
    }


def get_capacity_targets(configs: "_types.ManagerConfigs") -> typing.Dict[str, dict]:
    """
    Determine the desired capacity within the cluster.

    Handles allocation for each of the ec2 fleets that manage the worker nodes.
    """
    capacities = _controller.get_pods(configs)
    nodes = {}
    for requirements in configs.fleets:
        if fleet := _controller.get_fleet(configs, requirements):
            nodes.update(_controller.get_nodes(configs, fleet) or {})

    # Allocate pods into their ideal fleet and then repack smaller pods into
    # larger nodes where there is excess allocated capacity.
    memberships: typing.Dict[
        _types.FleetRequirements, typing.Dict[_types.CapacityItem, float]
    ] = {f: allocate(f, capacities, nodes) for f in configs.fleets}

    for requirements, members in memberships.items():
        repack(requirements, members, memberships)

    for requirements, members in memberships.items():
        _create_fleet_allocation(requirements, members)

    if len(capacities) != sum([len(a) for a in memberships.values()]):
        # If for some reason not all pods could be scheduled, an error
        # should be raised to alert monitors that scheduling isn't working
        # at the moment.
        raise ValueError(
            "Not all pods were able to be allocated to a fleet due to "
            "mismatched resource constraints."
        )

    return {
        fleet.name: _create_fleet_allocation(fleet, members)
        for fleet, members in memberships.items()
    }
