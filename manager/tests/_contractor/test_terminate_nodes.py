from unittest.mock import MagicMock
from unittest.mock import patch

from manager import _configs
from manager import _contractor
from manager.tests import _utils
from manager import _types


@patch("manager._controller.get_nodes")
def test_terminate_nodes(get_nodes: MagicMock):
    """Should terminate nodes without error."""
    configs = _types.ManagerConfigs()
    configs.fleets.append(
        _types.FleetRequirements(
            configs=configs,
            sector="primary",
            size_spec=_types.SMALL_MEMORY_SPEC,
        )
    )

    get_nodes.return_value = {
        "a": _utils.make_fleet_node(
            name="a",
            requirements=configs.fleets[0],
            is_unblocked=True,
            state=_configs.TERMINATING_STATE,
        ),
        "b": _utils.make_fleet_node(
            name="b",
            requirements=configs.fleets[0],
            is_unblocked=False,
            state=_configs.WARMING_UP_STATE,
        ),
        "c": _utils.make_fleet_node(
            name="c",
            requirements=configs.fleets[0],
            is_unblocked=True,
            state=_configs.WARMING_UP_STATE,
        ),
        "d": _utils.make_fleet_node("d", configs.fleets[0]),
        "e": _utils.make_fleet_node("e", configs.fleets[0]),
    }
    fleet = _utils.make_fleet(configs.fleets[0], 3)
    result = _contractor.terminate_nodes(MagicMock(), fleet)
    assert len(result) == 2
    assert {"a", "c"} == set([n.name for n in result])


@patch("manager._controller.get_nodes")
def test_terminate_nodes_blocked(get_nodes: MagicMock):
    """Should abort terminating nodes because none are ready for termination."""
    configs = _types.ManagerConfigs()
    configs.fleets.append(
        _types.FleetRequirements(
            configs=configs,
            sector="primary",
            size_spec=_types.SMALL_MEMORY_SPEC,
        )
    )

    get_nodes.return_value = {
        "a": _utils.make_fleet_node("a", configs.fleets[0]),
        "b": _utils.make_fleet_node(
            name="b",
            requirements=configs.fleets[0],
            state=_configs.WARMING_UP_STATE,
            seconds_old=123,
        ),
        "c": _utils.make_fleet_node("c", configs.fleets[0]),
        "d": _utils.make_fleet_node("d", configs.fleets[0]),
    }
    fleet = _utils.make_fleet(configs.fleets[0], 3)
    result = _contractor.terminate_nodes(MagicMock(), fleet)
    assert len(result) == 0
