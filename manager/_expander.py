from manager import _controller
from manager import _types


def grow_fleet(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
    target_capacity: int,
) -> bool:
    """
    Carry out a capacity growth action for the specified fleet if applicable.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet:
        Description of the fleet to be modified.
    :param target_capacity:
        New desired capacity to set the fleet capacity value to.
    """
    if fleet.capacity >= target_capacity:
        return True

    success = _controller.adjust_fleet(configs, fleet, target_capacity)
    if not success:
        print(f"Failed to grow {fleet.name} fleet capacity.")
    else:
        print(f"Growing {fleet.name} fleet capacity to {target_capacity}.")
    return success
