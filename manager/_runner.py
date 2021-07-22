import dataclasses
import datetime
import pathlib
import time
import traceback
import typing

import kuber

from manager import _allocator
from manager import _configs
from manager import _contractor
from manager import _controller
from manager import _expander
from manager import _types


@dataclasses.dataclass()
class Status:
    """Data structure for cross-execution-loop status."""

    recent_error_count: int = 0
    last_logged: datetime.datetime = dataclasses.field(
        default_factory=lambda: datetime.datetime(2000, 1, 1)
    )
    previous_allocations: typing.Dict[str, typing.Any] = dataclasses.field(
        default_factory=lambda: {}
    )

    @property
    def seconds_since_logged(self) -> float:
        """Compute number of seconds since the last logged action."""
        return (datetime.datetime.utcnow() - self.last_logged).total_seconds()


def _update_fleet(
    configs: "_types.ManagerConfigs",
    fleet_requirements: "_types.FleetRequirements",
    desired_capacity: int,
) -> typing.Dict[str, typing.Any]:
    """
    Determine what, if any, fleet capacity changes should be applied.

    This is based on current resource and node capacity. Operations here are idempotent
    and expressed in terms of a desired capacity for the fleet to prevent any possible
    race conditions from wildly auto-scaling resources.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet_requirements:
        Requirements object defining the fleet on which to update.
    :param desired_capacity:
        Number of nodes that should be available within the cluster based on
        pod capacity needs determined elsewhere.
    """
    fleet = _controller.get_fleet(configs, fleet_requirements)
    if not fleet:
        return {
            "fleet": fleet_requirements.name,
            "error": "FLEET_NOT_FOUND",
            "nodes": [],
            "node_capacities": {},
        }

    fleet_nodes = list(_controller.get_nodes(configs, fleet).values())
    active_nodes = [n for n in fleet_nodes if n.state == _configs.ACTIVE_STATE]

    node_log_data = []
    for node in fleet_nodes:
        node_log_data.append(
            {
                "name": node.name,
                "instance_id": node.instance_id,
                "current_state": node.state.upper(),
                "is_unblocked": node.is_unblocked,
                "pods": [pod_id for pod_id, item in node.pods.items()],
            }
        )

    if not configs.dry_run:
        _contractor.shrink_fleet(configs, fleet, desired_capacity)
        _expander.grow_fleet(configs, fleet, desired_capacity)

    return {
        "node_capacities": {
            "active": len(active_nodes),
            "desired": desired_capacity,
            "fleet_current": len(fleet_nodes),
            "fleet_target": fleet.capacity,
            "unfilled": max(0, desired_capacity - len(active_nodes)),
        },
        "nodes": node_log_data,
    }


def _execute(
    configs: "_types.ManagerConfigs",
    args: typing.Dict[str, typing.Any],
    status: "Status",
    config_path_override: typing.Union[str, pathlib.Path] = None,
):
    """Execute a management action within the kluster."""
    # Access config must be loaded within the loop because it
    # creates temporary credentials and won't survive for an
    # extended period of time outside of the loop.
    kuber.load_access_config(in_cluster=not configs.external)

    # Update each of the fleets according to the computed capacity
    # requirements.
    allocations = _allocator.get_capacity_targets(configs)
    for fleet_name, allocation in allocations.items():
        allocation.update(
            _update_fleet(
                configs,
                typing.cast(
                    # This must exist because it was already specified in allocations.
                    _types.FleetRequirements,
                    configs.get_fleet_requirements_by_name(fleet_name),
                ),
                int(allocation["capacity"]["target"]),
            )
        )

    # Handle status updates as needed after the allocation updates.
    status.recent_error_count = max(0, status.recent_error_count - 1)
    changing = status.previous_allocations != allocations
    status.previous_allocations = allocations

    # Log when there are changes or the max logging interval threshold has been reached.
    now = datetime.datetime.utcnow()
    if changing or status.seconds_since_logged >= configs.max_logging_interval:
        status.last_logged = now
        configs.log(
            "Reallocating",
            {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "recent_error_count": status.recent_error_count,
                "changing": changing,
                **{k: v for k, v in allocations.items() if not v["is_empty"]},
            },
        )


def main(
    args: typing.Dict[str, typing.Any],
    config_path_override: typing.Union[str, pathlib.Path] = None,
) -> int:
    """
    Iterate an unending loop that handles resizing a cluster.

    Each iteration has  a sleep between intervals in which each interval checks the
    current state of the cluster pods resources against the available node resources
    and either grows or shrinks the number of nodes in the cluster as needed.

    :param args:
        Arguments parsed from the command line. These arguments will take precedence
        over arguments specified by other means during execution.
    :param config_path_override:
        An override for the config path that is only used during non-normal execution
        calls. Most commonly this will be for testing purposes, but alternative calling
        implementations of this code could utilize this as well.
    """
    configs = _types.ManagerConfigs().load(args, config_path_override)
    configs.log("starting", configs.to_dict())

    status = Status()
    while status.recent_error_count < configs.critical_error_threshold:
        time.sleep(configs.sleep_interval)

        if configs.seconds_old > configs.config_refresh_interval:
            # Refresh the configs every so often to ensure any configuration changes
            # will be applied to future allocations. This allows the configuration
            # specified via a ConfigMap object to be updated and apply to this running
            # instance.
            configs.load(args, config_path_override)

        try:
            _execute(configs, args, status, config_path_override)
        except Exception as error:
            # Catch errors, print them and then begin the loop again.
            # There are a lot of reasons for transient errors here that
            # are not critical failures. However, the accumulation of
            # lots of errors in a row become critical and logging should
            # raise that concern.
            traceback.print_exc()
            print(f"{type(error)}: {error}")
            status.recent_error_count += 1

    return status.recent_error_count
