import math
from unittest.mock import MagicMock

from pytest import mark

from manager import _allocator

SCENARIOS = (
    {"min": 0, "capacities": [0.72, 0.72, 0.72, 0.72], "expected": 4},
    {"min": 5, "capacities": [0.72, 0.72, 0.72, 0.72], "expected": 5},
    {"min": 0, "capacities": [], "expected": 0},
    {"min": 0, "capacities": [0.25, 0.25, 0.25], "expected": 1},
    {"min": 0, "capacities": [0.5, 0.75, 0.25], "expected": 2},
    {
        "min": 0,
        "capacities": [0.4, 0.2, 0.04, 0.04, 0.40, 0.40, 0.32, 0.08, 1.00],
        "expected": 3,
    },
    {
        "min": 0,
        "capacities": [0.25, 0.75, 0.25],
        # Pods that no longer need resource allocations should not use capacity.
        "no_resource_capacities": [1.0, 10.0, 20.0],
        "expected": 2,
    },
)


@mark.parametrize("scenario", SCENARIOS)
def test_compute_fleet_capacity(scenario: dict):
    """Should calculate the expected fleet capacity for each scenario."""
    fleet = MagicMock(capacity_min=scenario["min"])
    members = {MagicMock(needs_resources=True): c for c in scenario["capacities"]}
    members.update(
        {
            MagicMock(needs_resources=False): c
            for c in scenario.get("no_resource_capacities", [])
        }
    )
    result = _allocator._compute_fleet_capacity(fleet, members)
    assert scenario["expected"] == int(math.ceil(result))
