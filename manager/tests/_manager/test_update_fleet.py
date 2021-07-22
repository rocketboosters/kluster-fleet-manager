import dataclasses
from unittest.mock import MagicMock
from unittest.mock import patch

import lobotomy
from pytest import mark

from manager import _runner
from manager import _types
from manager.tests import _utils

CAPACITY_SCENARIOS = (
    {"desired": 4, "fleet": 2, "node": 2},
    {"desired": 0, "fleet": 0, "node": 0},
    {"desired": 0, "fleet": 0, "node": 2},
    {"desired": 0, "fleet": 2, "node": 0},
    {"desired": 2, "fleet": 1, "node": 3},
)


@mark.parametrize("scenario", CAPACITY_SCENARIOS)
@lobotomy.patch()
@patch("manager._expander.grow_fleet")
@patch("manager._contractor.shrink_fleet")
@patch("manager._controller.get_nodes")
@patch("manager._controller.get_fleet")
def test_update_fleet(
    get_fleet: MagicMock,
    get_nodes: MagicMock,
    shrink_fleet: MagicMock,
    grow_fleet: MagicMock,
    lobotomized: lobotomy.Lobotomy,
    scenario: dict,
):
    """Should update the fleet by calling the shrink and grow functions."""
    configs = _types.ManagerConfigs()
    configs.fleets.append(
        _types.FleetRequirements(
            configs=configs,
            sector="primary",
            size_spec=_types.SMALL_MEMORY_SPEC,
        )
    )

    get_fleet.return_value = _utils.make_fleet(
        requirements=configs.fleets[0],
        capacity=scenario["fleet"],
    )

    node = _utils.make_fleet_node("a", configs.fleets[0])
    indexes = list(range(scenario["node"]))
    get_nodes.return_value = {
        **{f"a{i}": node for i in indexes},
        # These nodes should be filtered out because they don't meet the
        # criteria for inclusion in the fleet capacity calculation.
        **{f"b{i}": dataclasses.replace(node, state="foo") for i in indexes},
        **{
            f"c{i}": dataclasses.replace(node, requirements=configs.fleets[0])
            for i in indexes
        },
    }

    _runner._update_fleet(
        configs=configs,
        fleet_requirements=configs.fleets[0],
        desired_capacity=scenario["desired"],
    )
