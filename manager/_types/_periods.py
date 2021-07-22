import dataclasses
import datetime
import re
import typing

_HOUR_REGEX = re.compile(r"(?P<hour>[0-9]+)")
_HOUR_MINUTE_REGEX = re.compile(r"(?P<hour>[0-9]+):(?P<minute>[0-9]+)")
_TIME_REGEX = re.compile(r"(?P<hour>[0-9]+):(?P<minute>[0-9]+):(?P<second>[0-9]+)")


def _to_time(value: str) -> datetime.time:
    """
    Convert a string value time into a time object.

    Expects a format of `(H)H` or `(H):MM` or `(H)H:MM:SS`.
    """
    match = (
        _TIME_REGEX.match(value.strip())
        or _HOUR_MINUTE_REGEX.match(value.strip())
        or _HOUR_REGEX.match(value.strip())
    )
    if not match:
        raise ValueError(f"Unable to parse time value '{value}'")

    try:
        return datetime.time(
            hour=int(match.group("hour")),
            minute=int(match.groupdict().get("minute", 0)),
            second=int(match.groupdict().get("second", 0)),
        )
    except ValueError as error:
        raise ValueError(f'Invalid time value of "{value}".') from error


def _time_between(earlier: datetime.time, later: datetime.time) -> int:
    """Calculate the number of seconds between two times."""
    return (
        3600 * (later.hour - earlier.hour)
        + 60 * (later.minute - earlier.minute)
        + later.second
        - earlier.second
    )


def _to_day_seconds(value: typing.Union[str, datetime.time, int]) -> int:
    """Convert a time-like value into a number of seconds since midnight."""
    if isinstance(value, str):
        return _time_between(datetime.time(), _to_time(value))

    if isinstance(value, datetime.time):
        return _time_between(datetime.time(), value)

    if isinstance(value, int):
        return value


def grace_periods_from_config(
    data: typing.List[typing.Dict[str, typing.Any]] = None,
) -> typing.List["InactiveGracePeriod"]:
    """
    Parse inactive_grace_period config data into a prioritized list of grace periods.

    If an empty list or null is provided, the returned value will be a single length
    list with the default grace period that covers the entire day.
    """
    default_period = InactiveGracePeriod.from_config({})
    output = [InactiveGracePeriod.from_config(item) for item in data or []]
    output.append(default_period)
    return output


@dataclasses.dataclass(frozen=True)
class InactiveGracePeriod:
    """Data structure for node termination inactive grace period configurations."""

    day_seconds_starts: int
    day_seconds_ends: int
    value: int
    days_of_week: typing.Tuple[str, ...] = dataclasses.field(
        default_factory=lambda: tuple()
    )

    def in_range_of(self, date_time: datetime.datetime = None) -> bool:
        """
        Determine if the specified time or now is in the range of this period.

        The returned value will be true if the time resides within the partially
        close [start, end) range for this InactiveGracePeriod instance. Overnight
        values are supported where the end value is an earlier time than the start.
        Days of week are also taken into account.
        """
        now = date_time or datetime.datetime.utcnow()
        # 1 is Monday, 7 is Sunday
        iso_day_of_week = int(now.strftime("%u"))

        if self.days_of_week and iso_day_of_week not in self.days_of_week:
            return False

        value = _to_day_seconds(now.time())

        s = self.day_seconds_starts
        e = self.day_seconds_ends
        return (
            (s < e and s <= value < e)
            # Overnight where the end is less than the start and the value is later
            # in the evening (after start) but before midnight.
            or (e < s <= value)
            # Overnight where the end is less than the start and the value is earlier
            # in the morning (before end) but after midnight.
            or (s > e > value)
        )

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        """Convert to a dictionary representation that is JSON serializable for logs."""
        return {
            "day_seconds_start": self.day_seconds_starts,
            "day_seconds_ends": self.day_seconds_ends,
            "value": self.value,
            "in_range_of_now": self.in_range_of(),
            "days_of_weeks": list(self.days_of_week) or None,
        }

    @classmethod
    def from_config(cls, data: typing.Dict[str, typing.Any]) -> "InactiveGracePeriod":
        """Create an InactiveGracePeriod instance from config file data."""
        return cls(
            day_seconds_starts=_to_day_seconds(data.get("starts", 0)),
            day_seconds_ends=_to_day_seconds(data.get("ends", 86400)),
            value=int(data.get("value", 600)),
            days_of_week=tuple(data.get("days") or []),
        )
