import dataclasses
import typing

FLEET_SIZES = {
    "small": "small",
    "s": "small",
    "medium": "medium",
    "m": "medium",
    "large": "large",
    "l": "large",
    "xlarge": "xlarge",
    "xl": "xlarge",
}

FLEET_KINDS = {
    "memory": "memory",
    "cpu": "cpu",
}


@dataclasses.dataclass(frozen=True)
class InstanceType:
    """Data structure for an EC2 instance type."""

    name: str
    cpu: float
    memory: int


@dataclasses.dataclass(frozen=True)
class FleetSizeSpecification:
    """Data structure containing t-shirt-size-specific specifications."""

    #: Size of the fleet nodes, which identifies the fleet within the
    #: sector as each sector should only have one fleet for a given size.
    size: str
    #: The optimized resource allocation for this fleet.
    kind: str
    #: A relative scale of this fleet within its sector. This is used
    #: during capacity planning to repack capacity into other fleets
    #: in the same sector where excess capacity exists. The smallest
    #: fleet in a sector should have a value of 1 and larger fleets
    #: a multiple of that representing the relative scale of them to
    #: their peers.
    # capacity_weight: int

    #: EC2 instance types.
    instance_types: typing.Tuple["InstanceType", ...]

    @property
    def memory_max(self) -> int:
        """
        Maximum memory in bytes for the nodes in this fleet.

        Nothing should be scheduled in this fleet that meets or exceeds this limit.
        """
        return min([x.memory for x in self.instance_types])

    @property
    def cpu_max(self) -> float:
        """
        Maximum vCPU units for the nodes in this fleet.

        Nothing should be scheduled in this fleet that meets or exceeds this limit.
        """
        return min([x.cpu for x in self.instance_types])

    @property
    def lookup_key(self) -> str:
        """Fleet size specification lookup key used internally."""
        return f"{self.size}-{self.kind}"

    def smaller_than(self, other: "FleetSizeSpecification") -> bool:
        """
        Compare with other fleet size spec.

        :return:
            Whether this fleet size spec is smaller than the other one.
        """
        if self.kind == "memory":
            return self.memory_max < other.memory_max
        return self.cpu_max < other.cpu_max


XSMALL_MEMORY_SPEC = FleetSizeSpecification(
    size="xsmall",
    kind="memory",
    instance_types=(
        InstanceType("r4.large", 2.0, int(15.25 * 1024 ** 3)),
        InstanceType("r5.large", 2.0, 16 * 1024 ** 3),
        InstanceType("m4.xlarge", 4.0, 16 * 1024 ** 3),
        InstanceType("m5.xlarge", 4.0, 16 * 1024 ** 3),
    ),
)

XSMALL_CPU_SPEC = FleetSizeSpecification(
    size="xsmall",
    kind="cpu",
    instance_types=(
        InstanceType("c4.xlarge", 4.0, int(7.5 * 1024 ** 3)),
        InstanceType("c5.xlarge", 4.0, 8 * 1024 ** 3),
        InstanceType("m4.xlarge", 4.0, 16 * 1024 ** 3),
        InstanceType("m5.xlarge", 4.0, 16 * 1024 ** 3),
    ),
)

SMALL_MEMORY_SPEC = FleetSizeSpecification(
    size="small",
    kind="memory",
    instance_types=(
        InstanceType("r4.xlarge", 4.0, int(30.5 * 1024 ** 3)),
        InstanceType("r5.xlarge", 4.0, 32 * 1024 ** 3),
        InstanceType("m4.2xlarge", 8.0, 32 * 1024 ** 3),
        InstanceType("m5.2xlarge", 8.0, 32 * 1024 ** 3),
    ),
)

SMALL_CPU_SPEC = FleetSizeSpecification(
    size="small",
    kind="cpu",
    instance_types=(
        InstanceType("c4.2xlarge", 8.0, 15 * 1024 ** 3),
        InstanceType("c5.2xlarge", 8.0, 16 * 1024 ** 3),
        InstanceType("m4.2xlarge", 8.0, 32 * 1024 ** 3),
        InstanceType("m5.2xlarge", 8.0, 32 * 1024 ** 3),
    ),
)

MEDIUM_MEMORY_SPEC = FleetSizeSpecification(
    size="medium",
    kind="memory",
    instance_types=(
        InstanceType("r4.2xlarge", 8.0, 61 * 1024 ** 3),
        InstanceType("r5.2xlarge", 8.0, 64 * 1024 ** 3),
        InstanceType("m4.4xlarge", 16.0, 64 * 1024 ** 3),
        InstanceType("m5.4xlarge", 16.0, 64 * 1024 ** 3),
    ),
)

MEDIUM_CPU_SPEC = FleetSizeSpecification(
    size="medium",
    kind="cpu",
    instance_types=(
        InstanceType("c4.4xlarge", 16.0, 30 * 1024 ** 3),
        InstanceType("c5.4xlarge", 16.0, 32 * 1024 ** 3),
        InstanceType("m4.4xlarge", 16.0, 64 * 1024 ** 3),
        InstanceType("m5.4xlarge", 16.0, 64 * 1024 ** 3),
    ),
)

LARGE_MEMORY_SPEC = FleetSizeSpecification(
    size="large",
    kind="memory",
    instance_types=(
        InstanceType("r4.4xlarge", 16.0, 122 * 1024 ** 3),
        InstanceType("r5.4xlarge", 16.0, 128 * 1024 ** 3),
        InstanceType("m4.10xlarge", 40.0, 160 * 1024 ** 3),
        InstanceType("m5.8xlarge", 32.0, 128 * 1024 ** 3),
    ),
)

LARGE_CPU_SPEC = FleetSizeSpecification(
    size="large",
    kind="cpu",
    instance_types=(
        InstanceType("c4.8xlarge", 36.0, 60 * 1024 ** 3),
        InstanceType("c5.9xlarge", 36.0, 72 * 1024 ** 3),
        InstanceType("m4.10xlarge", 40.0, 160 * 1024 ** 3),
        InstanceType("m5.12xlarge", 48.0, 192 * 1024 ** 3),
    ),
)

XLARGE_MEMORY_SPEC = FleetSizeSpecification(
    size="xlarge",
    kind="memory",
    instance_types=(
        InstanceType("r4.8xlarge", 32.0, 244 * 1024 ** 3),
        InstanceType("r5.8xlarge", 32.0, 256 * 1024 ** 3),
        InstanceType("m4.16xlarge", 64.0, 256 * 1024 ** 3),
        InstanceType("m5.16xlarge", 64.0, 256 * 1024 ** 3),
    ),
)

XLARGE_CPU_SPEC = FleetSizeSpecification(
    size="xlarge",
    kind="cpu",
    instance_types=(
        InstanceType("c5.18xlarge", 72.0, 144 * 1024 ** 3),
        InstanceType("m4.16xlarge", 64.0, 256 * 1024 ** 3),
        InstanceType("m5.16xlarge", 64.0, 256 * 1024 ** 3),
    ),
)

_FLEET_OPTIONS = {
    XSMALL_MEMORY_SPEC.lookup_key: XSMALL_MEMORY_SPEC,
    XSMALL_CPU_SPEC.lookup_key: XSMALL_CPU_SPEC,
    SMALL_MEMORY_SPEC.lookup_key: SMALL_MEMORY_SPEC,
    SMALL_CPU_SPEC.lookup_key: SMALL_CPU_SPEC,
    MEDIUM_MEMORY_SPEC.lookup_key: MEDIUM_MEMORY_SPEC,
    MEDIUM_CPU_SPEC.lookup_key: MEDIUM_CPU_SPEC,
    LARGE_MEMORY_SPEC.lookup_key: LARGE_MEMORY_SPEC,
    LARGE_CPU_SPEC.lookup_key: LARGE_CPU_SPEC,
    XLARGE_MEMORY_SPEC.lookup_key: XLARGE_MEMORY_SPEC,
    XLARGE_CPU_SPEC.lookup_key: XLARGE_CPU_SPEC,
}


def get_fleet_size_specification(size: str, kind: str) -> FleetSizeSpecification:
    """Get the FleetSizeSpecification for the given size adn kind values."""
    try:
        return _FLEET_OPTIONS[f"{size}-{kind}"]
    except KeyError:
        raise ValueError(f"Unknown fleet configuration of '{size}' and '{kind}'.")
