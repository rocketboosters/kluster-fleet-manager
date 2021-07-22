from datetime import datetime

from pytest import mark

from manager import _types

SCENARIOS = [
    # These should be in the first grace period.
    ("2021-07-19T09:30:00", 1200),
    ("2021-07-19T08:00:00", 1200),
    ("2021-07-19T13:59:00", 1200),
    # These should be in the second grace period.
    ("2021-07-20T22:00:00", 1600),
    ("2021-07-20T03:59:59", 1600),
    # These should be in the third grace period.
    ("2021-07-20T19:00:00", 42),
    ("2021-07-21T19:59:59", 42),
    # These should be in the default grace period.
    ("2021-07-20T09:30:00", 600),
]


@mark.parametrize("timestamp, expected", SCENARIOS)
def test_get_inactive_grace_period(
    timestamp: str,
    expected: int,
):
    """Should return expected grace period based on time."""
    date_time = datetime.fromisoformat(timestamp)
    configs = _types.ManagerConfigs()
    configs.inactive_grace_periods = [
        _types.InactiveGracePeriod.from_config(
            {"starts": "8:00", "ends": "14:00", "value": 1200, "days": [1]}
        ),
        _types.InactiveGracePeriod.from_config(
            {"starts": "22:00", "ends": "4:00", "value": 1600, "days": [2]}
        ),
        _types.InactiveGracePeriod.from_config(
            {"starts": "19:00", "ends": "20:00", "value": 42, "days": None}
        ),
        _types.InactiveGracePeriod.from_config({}),
    ]
    observed = configs.get_inactive_grace_period(date_time)
    assert observed == expected
