import dataclasses
import datetime
import json
import os
import pathlib
import typing

import boto3
import yaml

from manager import _conversions
from manager import _types


def _or(*args: typing.Any, default: typing.Any = None) -> typing.Any:
    """
    Find the first non-None element in the args.

    If none of the values are not None, the default value will be returned instead.
    """
    return next((x for x in args if x is not None), default)


def _or_truthy(*args: typing.Any, default: typing.Any = None) -> typing.Any:
    """
    Find the first truthy element in the args.

    If none of the values are truthy, the default value will be returned instead.
    """
    return next((x for x in args if x), default)


def _load_configs(
    args: typing.Dict[str, typing.Any],
    config_path: typing.Union[str, pathlib.Path] = None,
) -> typing.Dict[str, typing.Any]:
    """
    Load configuration data from the config path.

    Config path lookup is prioritized in the following way:
    - config_path argument specified in this function signature.
    - `--config-path` command line argument.
    - CONFIG_PATH environmental variable.
    - Default value of "/application/config/config.yaml"

    If the config file fails to load because the file is not found, a blank
    configuration will be used instead.
    """
    p = pathlib.Path(
        config_path
        or args.get("config_path")
        or os.environ.get("CONFIG_PATH")
        or "/application/config/config.yaml"
    )
    try:
        return yaml.safe_load(p.resolve().read_text())
    except FileNotFoundError:
        return {}


@dataclasses.dataclass()
class ManagerConfigs:
    """Configuration data structure for kluster fleet manager operation."""

    cluster_name: typing.Optional[str] = None
    aws_profile: typing.Optional[str] = None
    default_sector: typing.Optional[str] = None
    external: bool = False
    live: bool = False
    pretty_print: bool = False
    critical_error_threshold: int = 100
    sleep_interval: int = 20
    default_over_subscription: float = 0.2
    reserved_cpus: float = 1.0
    reserved_memory: int = int(2.5 * 1000 ** 3)
    config_refresh_interval: float = 60
    max_logging_interval: float = 120
    session: boto3.Session = dataclasses.field(
        hash=False, default_factory=lambda: boto3.Session()
    )
    fleets: typing.List["_types.FleetRequirements"] = dataclasses.field(
        hash=False,
        default_factory=lambda: [],
    )
    inactive_grace_periods: typing.List[
        "_types.InactiveGracePeriod"
    ] = dataclasses.field(
        hash=False, default_factory=lambda: [_types.InactiveGracePeriod.from_config({})]
    )
    last_loaded_at: datetime.datetime = dataclasses.field(
        default_factory=lambda: datetime.datetime.utcnow()
    )

    @property
    def default_fleet_sector(self) -> str:
        """Name of the default sector to apply for pods not assigned to one."""
        if self.default_sector:
            return self.default_sector

        if not self.fleets:
            return "unknown"

        return self.fleets[0].sector

    @property
    def dry_run(self) -> bool:
        """
        Whether this manager is in dry-run mode.

        When running in dry-run mode, the manager will compute and echo fleet changes
        without actually executing any resizing actions.
        """
        return not self.live

    @property
    def seconds_old(self) -> int:
        """Compute number of seconds since this config was created/refreshed."""
        return int((datetime.datetime.utcnow() - self.last_loaded_at).total_seconds())

    def get_inactive_grace_period(self, date_time: datetime.datetime = None) -> int:
        """
        Get the applicable inactive grace period for the given time.

        If no time is specified, it will return the value for the current UTC now time.
        """
        finder = (
            p.value for p in self.inactive_grace_periods if p.in_range_of(date_time)
        )
        return next(finder, 600)

    def get_fleet_requirements(
        self,
        sector: str,
        size: str,
    ) -> typing.Optional["_types.FleetRequirements"]:
        """Find the fleet requirements given sector and size values."""
        finder = (f for f in self.fleets if f.sector == sector and f.size == size)
        return next(finder, None)

    def get_fleet_requirements_by_name(
        self,
        fleet_name: str,
    ) -> typing.Optional["_types.FleetRequirements"]:
        """Find the fleet requirements for the given name: '{sector}-{size}'."""
        sector, size = fleet_name.split("-")
        return self.get_fleet_requirements(sector, size)

    def get_smaller_fleet(
        self,
        fleet_requirements: "_types.FleetRequirements",
    ) -> typing.Optional["_types.FleetRequirements"]:
        """
        Find the smaller fleet in the same sector as the specified one.

        :return:
            The fleet requirements for the smaller fleet within the same sector. If
            no such fleet exists, a None value will be returned instead.
        """
        matches = [
            f
            for f in self.fleets
            if f.sector == fleet_requirements.sector
            and f.size_spec.smaller_than(fleet_requirements.size_spec)
        ]
        if fleet_requirements.size_spec.kind == "memory":
            matches = list(
                sorted(matches, key=lambda x: x.size_spec.memory_max, reverse=True)
            )
        else:
            matches = list(sorted(matches, key=lambda x: x.size_spec.cpu_max))

        return matches[0] if matches else None

    def get_sector_fleets(
        self,
        sector_name: str,
    ) -> typing.List["_types.FleetRequirements"]:
        """List all fleets in the specified sector."""
        matches = [f for f in self.fleets if f.sector == sector_name]
        matches.sort(key=lambda f: f.capacity_weight)
        return list(matches)

    def load(
        self,
        args: typing.Dict[str, typing.Any],
        config_path: typing.Union[str, pathlib.Path] = None,
    ) -> "ManagerConfigs":
        """
        Populate manager config with data from a config file.

        Config path lookup is prioritized in the following way:
        - config_path argument specified in this function signature.
        - `--config-path` command line argument.
        - CONFIG_PATH environmental variable.
        - Default value of "/application/config/config.yaml"

        If none of these exist, the default values will be loaded instead.
        """
        self.last_loaded_at = datetime.datetime.utcnow()
        raw = _load_configs(args, config_path)

        self.cluster_name = _or_truthy(
            args.get("cluster_name"),
            os.environ.get("CLUSTER_NAME"),
            raw.get("cluster_name"),
        )
        if not self.cluster_name:  # pragma: no cover
            raise ValueError("A cluster name must be supplied.")

        self.aws_profile = _or(args.get("aws_profile"), self.aws_profile)
        self.default_sector = _or(raw.get("default_sector"), self.default_sector)
        self.external = _or_truthy(self.external, args.get("external"), False)
        self.live = _or_truthy(self.live, args.get("live"), False)
        self.pretty_print = _or_truthy(
            self.pretty_print, args.get("pretty_print"), False
        )
        self.critical_error_threshold = _or(raw.get("critical_error_threshold"), 100)
        self.sleep_interval = _or(raw.get("sleep_interval"), 20)
        self.default_over_subscription = _or(raw.get("default_over_subscription"), 0.2)
        self.reserved_cpus = _conversions.to_cpus(_or(raw.get("reserved_cpus"), 1.0))
        self.reserved_memory = _conversions.to_bytes(
            _or(raw.get("reserved_memory"), int(2.5 * 1000 ** 3))
        )
        self.config_refresh_interval = _or(raw.get("config_refresh_interval"), 60)
        self.max_logging_interval = _or(raw.get("max_logging_interval"), 120)

        self.session = boto3.Session(profile_name=self.aws_profile)
        self.fleets = _types.fleets_from_config(self, raw.pop("sectors", {}))
        self.inactive_grace_periods = _types.grace_periods_from_config(
            raw.pop("inactive_grace_periods", [])
        )

        return self

    def log(self, message: str, data: dict):
        """Log the message and data for structured output."""
        print(
            json.dumps(
                {"message": message, "data": data},
                indent=2 if self.pretty_print else None,
            )
        )

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        """Convert to a dictionary representation that is JSON serializable for logs."""
        return {
            "cluster_name": self.cluster_name,
            "aws_profile": self.aws_profile,
            "external": self.external,
            "live": self.live,
            "critical_error_threshold": self.critical_error_threshold,
            "sleep_interval": self.sleep_interval,
            "default_over_subscription": self.default_over_subscription,
            "reserved_cpus": self.reserved_cpus,
            "reserved_memory": self.reserved_memory,
            "last_loaded_at": str(self.last_loaded_at),
            "inactive_grace_periods": [
                p.to_dict() for p in self.inactive_grace_periods
            ],
            "fleets": [f.to_dict() for f in self.fleets],
        }
