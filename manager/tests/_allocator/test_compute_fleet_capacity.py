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
)


@mark.parametrize("scenario", SCENARIOS)
def test_compute_fleet_capacity(scenario: dict):
    """Should calculate the expected fleet capacity for each scenario."""
    fleet = MagicMock(capacity_min=scenario["min"])
    members = {f"{i}": c for i, c in enumerate(scenario["capacities"])}
    result = _allocator._compute_fleet_capacity(fleet, members)
    assert scenario["expected"] == int(math.ceil(result))
