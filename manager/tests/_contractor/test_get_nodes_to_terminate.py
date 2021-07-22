from unittest.mock import MagicMock

from kuber.latest import core_v1
from pytest import mark

from manager import _types
from manager import _contractor

BLOCKED = MagicMock(
    name="blocked",
    is_unblocked=False,
    resource=core_v1.Node(),
    pods={"a": MagicMock(is_bouncable=False)},
)

BOUNCABLE = MagicMock(
    name="bouncable",
    is_unblocked=False,
    resource=core_v1.Node(),
    pods={"a": MagicMock(is_bouncable=True)},
)

BOUNCABLE_TWO = MagicMock(
    name="bouncable",
    is_unblocked=False,
    resource=core_v1.Node(),
    pods={"a": MagicMock(is_bouncable=True), "b": MagicMock(is_bouncable=True)},
)

UNBLOCKED = MagicMock(
    name="unblocked", is_unblocked=True, resource=core_v1.Node(), pods={}
)


SCENARIOS = [
    {
        # No reduce by should not return any nodes to terminate even
        # if they are unblocked or bouncable.
        "reduce_by": 0,
        "nodes": [BLOCKED, UNBLOCKED, BOUNCABLE_TWO, BOUNCABLE],
        "expected": [],
    },
    {
        # Reducing should always terminate unblocked nodes before resorting
        # to bouncable nodes.
        "reduce_by": 1,
        "nodes": [BLOCKED, UNBLOCKED, BOUNCABLE_TWO, BOUNCABLE],
        "expected": [UNBLOCKED],
    },
    {
        # Bouncable nodes should be added in order of increasing pod count
        # to minimize impact of the bounce.
        "reduce_by": 2,
        "nodes": [BLOCKED, UNBLOCKED, BOUNCABLE_TWO, BOUNCABLE],
        "expected": [UNBLOCKED, BOUNCABLE],
    },
    {
        # Don't terminate nodes that aren't unblocked or bouncable even if
        # the reduce by is greater than the number of available nodes in those
        # states.
        "reduce_by": 4,
        "nodes": [BLOCKED, UNBLOCKED, BOUNCABLE_TWO, BOUNCABLE],
        "expected": [UNBLOCKED, BOUNCABLE, BOUNCABLE_TWO],
    },
    {
        # Don't include bouncable nodes in fleets that have disabled
        # bouncing.
        "bouncable": False,
        "reduce_by": 4,
        "nodes": [BLOCKED, UNBLOCKED, BOUNCABLE_TWO, BOUNCABLE],
        "expected": [UNBLOCKED],
    },
]


@mark.parametrize("scenario", SCENARIOS)
def test_get_nodes_to_terminate(scenario: dict):
    """
    Should return the expected list of mocked FleetNodes for
    the given scenario.
    """
    configs = _types.ManagerConfigs()
    configs.fleets.append(
        _types.FleetRequirements(
            configs=configs,
            sector="foo",
            size_spec=_types.SMALL_MEMORY_SPEC,
            capacity_min=scenario.get("capacity_min", 0),
            bounce_deployment_pods=scenario.get("bouncable", True),
        )
    )

    results = _contractor._get_nodes_to_terminate(
        requirements=configs.fleets[0],
        fleet_nodes=scenario["nodes"],
        reduce_by=scenario["reduce_by"],
    )
    assert scenario["expected"] == results
