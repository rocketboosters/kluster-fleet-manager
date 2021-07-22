from unittest.mock import MagicMock
from unittest.mock import patch

import lobotomy

from manager import _runner
from manager import _types


@lobotomy.patch()
@patch("time.sleep")
@patch("kuber.load_access_config")
@patch("manager._types.ManagerConfigs.load")
@patch("manager._allocator.get_capacity_targets")
@patch("manager._runner._update_fleet")
def test_main(
    update_fleet: MagicMock,
    get_capacity_targets: MagicMock,
    manager_configs_load: MagicMock,
    kuber_load_access_config: MagicMock,
    time_sleep: MagicMock,
    lobotomized: lobotomy.Lobotomy,
):
    """Should execute the update loop 3 times and then stop."""
    configs = _types.ManagerConfigs()
    configs.critical_error_threshold = 1
    manager_configs_load.return_value = configs

    get_capacity_targets.return_value = {"primary-small": {"raw": 0.4, "desired": 1}}
    update_fleet.side_effect = [
        {},
        {},
        {},
        {},  # First iteration.
        {},
        {},
        {},
        {},  # Second iteration.
        ValueError("FAKE"),  # Third iteration should fail in error.
    ]

    result = _runner.main(
        {
            "cluster_name": "foo",
            "aws_profile": "fake",
            "external": True,
            "critical_error_threshold": 1,
        }
    )
    assert result == 1
    assert kuber_load_access_config.called
    assert time_sleep.called
