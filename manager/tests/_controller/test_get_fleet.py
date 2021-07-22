import lobotomy

from manager import _controller
from manager import _types

fleet_data = {
    "FleetId": "fleet-123",
    "Tags": [
        {"Key": "size", "Value": "small"},
        {"Key": "sector", "Value": "primary"},
        {"Key": "fleet", "Value": "primary-small"},
        {"Key": "Foo", "Value": "bar"},
    ],
    "TargetCapacitySpecification": {"TotalTargetCapacity": 2},
}


@lobotomy.patch()
def test_get_fleet(lobotomized: "lobotomy.Lobotomy"):
    """Should retrieve and transform EC2 fleet data into a Fleet."""
    lobotomized.add_call("ec2", "describe_fleets", {"Fleets": [fleet_data]})
    configs = _types.ManagerConfigs()
    fleet_requirements = _types.FleetRequirements(
        configs=configs,
        sector="primary",
        size_spec=_types.SMALL_MEMORY_SPEC,
    )

    fleet = _controller.get_fleet(configs, fleet_requirements)
    assert fleet.identifier == "fleet-123"
    assert fleet.sector == "primary"
    assert fleet.name == "primary-small"
    assert fleet.capacity == 2
