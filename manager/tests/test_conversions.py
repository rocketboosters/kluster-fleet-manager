import pytest
from pytest import mark

from manager import _conversions

MEMORY_SCENARIOS = (
    ("2K", 2000),
    ("2.1Ki", int(2.1 * 1024)),
    ("1.5M", int(1.5 * 1000 ** 2)),
    ("23G", 23 * 1000 ** 3),
    ("12.212Gi", int(12.212 * 1024 ** 3)),
    ("foo", 0),
    (None, 0),
)


@mark.parametrize("size, size_bytes", MEMORY_SCENARIOS)
def test_to_bytes(size: str, size_bytes: int):
    """Should convert the string size + units into a bytes integer."""
    assert size_bytes == _conversions.to_bytes(size)


CPU_SCENARIOS = (("2", 2.0), ("2.1", 2.1), ("210m", 0.21), ("", 0), (None, 0))


@mark.parametrize("cpu, cpu_value", CPU_SCENARIOS)
def test_to_cpus(cpu: str, cpu_value: float):
    """Should convert the string size + units into a bytes integer."""
    assert pytest.approx(cpu_value, _conversions.to_cpus(cpu))
