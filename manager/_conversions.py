import re
import typing

SIZE_REGEX = re.compile(r"(?P<value>[0-9.]+)(?P<units>.+)")

SIZE_SCALES = {
    "ki": 1024,
    "k": 1000,
    "mi": 1024 ** 2,
    "m": 1000 ** 2,
    "gi": 1024 ** 3,
    "g": 1000 ** 3,
}


def to_bytes(size: typing.Union[str, int]) -> int:
    """
    Convert a Kubernetes memory resource string into a bytes integer.

    For example, "50k", "2Gi", ..., will be converted into its representative bytes
    and returned as an integer.
    """
    if not size:
        return 0

    if not isinstance(size, str):
        return int(size)

    try:
        match = typing.cast(re.Match, SIZE_REGEX.match(size))
        if not match:
            return int(size)
        value = match.group("value")
        scale = SIZE_SCALES[match.group("units").lower()]
        return int(float(value) * scale)
    except Exception as error:
        print(f'[ERROR]: Unknown size identifier "{size}" ({error})')
        return 0


def to_cpus(size: typing.Union[str, int]) -> float:
    """
    Convert a Kubernetes CPU resource string into a float value.

    For example, "1", "1.2", "400m", ... will be converted into its representative
    float value.
    """
    try:
        return float(size or 0)
    except ValueError:
        # Handles milliCPU unit case
        return float(typing.cast(str, size).rstrip("m")) / 1000
