import typing
from unittest.mock import MagicMock

from kuber.latest import core_v1

from manager import _configs
from manager import _types


def make_fleet_node(
    name: str,
    requirements: _types.FleetRequirements,
    is_unblocked: bool = False,
    state: str = _configs.ACTIVE_STATE,
    resource: typing.Union[core_v1.Node, MagicMock] = None,
    instance_id: str = None,
    seconds_old: float = 3600,
    pods: dict = None,
):
    """Create a Mock fleet node for testing."""
    default_pods = {
        "foo:bar": _types.CapacityItem(
            pod_id="foo:bar",
            sector=requirements.sector,
            size=None,
            memory=123123123,
            cpu=1,
            pod=MagicMock(),
            status=MagicMock(),
        )
    }
    return _types.FleetNode(
        name=name,
        seconds_old=seconds_old,
        instance_id=instance_id or name,
        requirements=requirements,
        is_unblocked=is_unblocked,
        state=state,
        resource=resource or MagicMock(),
        pods=pods or default_pods,
    )


def make_fleet(
    requirements: "_types.FleetRequirements",
    capacity: int = 1,
) -> "_types.Fleet":
    """Create a mock Fleet from requirements."""
    return _types.Fleet(
        identifier="123abc",
        requirements=requirements,
        capacity=capacity,
        tags={
            "size": requirements.size,
            "sector": requirements.sector,
            "fleet": requirements.name,
        },
    )
