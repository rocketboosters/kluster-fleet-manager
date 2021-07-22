import lobotomy

from manager import _expander
from manager import _types
from manager.tests import _utils


def _make_configs() -> "_types.ManagerConfigs":
    """Create a configs object for testing."""
    configs = _types.ManagerConfigs()
    fleet_requirements = _types.FleetRequirements(
        configs=configs,
        sector="foo",
        size_spec=_types.SMALL_MEMORY_SPEC,
    )
    configs.fleets.append(fleet_requirements)
    return configs


@lobotomy.patch()
def test_grow_fleet(lobotomized: lobotomy.Lobotomy):
    """Should grow the fleet from current 1 to target 10 capacity."""
    lobotomized.add_call("ec2", "modify_fleet", {"Return": True})
    configs = _make_configs()

    fleet = _utils.make_fleet(configs.fleets[0], 1)
    assert _expander.grow_fleet(configs, fleet, 10)


@lobotomy.patch()
def test_grow_fleet_failed(lobotomized: lobotomy.Lobotomy):
    """Should fail to grow the fleet from current 1 to target 10 capacity."""
    lobotomized.add_call("ec2", "modify_fleet", {"Return": False})
    configs = _make_configs()

    fleet = _utils.make_fleet(configs.fleets[0], 1)
    assert not _expander.grow_fleet(configs, fleet, 10)


@lobotomy.patch()
def test_grow_fleet_unneeded(lobotomized: lobotomy.Lobotomy):
    """Should abort because capacity already exists."""
    lobotomized.add_call("ec2", "modify_fleet", {"Return": True})
    configs = _make_configs()

    fleet = _utils.make_fleet(configs.fleets[0], 10)
    assert _expander.grow_fleet(configs, fleet, 10)
    assert not lobotomized.get_service_calls("ec2", "modify_fleet")
