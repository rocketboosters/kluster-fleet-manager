import dataclasses
import typing

from kuber.latest import core_v1

from manager import _types


def fleets_from_config(
    config: "_types.ManagerConfigs",
    sectors_config: typing.Dict[str, typing.Dict[str, typing.Any]],
) -> typing.List["FleetRequirements"]:
    """Convert the sectors config data into fleet requirements."""
    return [
        FleetRequirements(
            configs=config,
            sector=sector,
            size_spec=_types.get_fleet_size_specification(
                size=fleet_data.get("size", "small"),
                kind=sector_data.get("kind", "memory"),
            ),
            capacity_min=fleet_data.get("capacity_min", 0),
            bounce_deployment_pods=fleet_data.get("bounce_deployment_pods", False),
        )
        for sector, sector_data in sectors_config.items()
        for fleet_data in sector_data.get("fleets", [])
    ]


@dataclasses.dataclass(frozen=True)
class FleetRequirements:
    """Data structure that expresses resource capacity bounds for a given ec2 fleet."""

    #: Shared configuration for all fleets.
    configs: "_types.ManagerConfigs" = dataclasses.field(hash=False, repr=False)
    #: One or more fleets combine to make up a sector of the cluster,
    #: which is a logical unit in which similar functionality is run.
    #: At the time of this documentation the cluster has an
    #: "primary" sector and a "coordinate" sector.
    sector: str
    #: Size specification settings for the fleet.
    size_spec: "_types.FleetSizeSpecification"
    #: Minimum amount of capacity allowed by this fleet. If zero, the
    #: fleet will be allowed to scale down to having no nodes running
    #: when not under any scheduling pressure. Set this above zero for
    #: fleets that should have nodes running at all times regardless of
    #: what is being scheduled on them.
    capacity_min: int = 0
    #: Whether or not deployments can flexibly be bounced from nodes
    #: that are not needed to meet target capacity requirements.
    bounce_deployment_pods: bool = False

    @property
    def name(self) -> str:
        """
        Identify the the fleet with a unique name.

        Fleets have a uniquely identifying name that matches the tag
        applied to them and that + cluster name are how they are
        identified and paired with a cluster.
        """
        return f"{self.sector}-{self.size}"

    @property
    def size(self) -> str:
        """
        Size of the fleet nodes.

        This identifies the fleet within the sector as each sector should only have
        one fleet for a given size. The size value also determines the EC2 instance
        types and associated memory/cpu that it supports.
        """
        return self.size_spec.size

    @property
    def memory_min(self) -> int:
        """
        Minimum memory in bytes that is ideally suited for this fleet.

        If multiple fleets exist in the same sector, this should be
        the same value as the maximum size of the smaller fleet in the same
        sector.
        """
        if smaller := self.configs.get_smaller_fleet(self):
            return smaller.memory_max
        return 0

    @property
    def memory_max(self) -> int:
        """
        Maximum memory in bytes for the nodes in this fleet.

        Nothing should be scheduled in this fleet that meets or exceeds this limit.
        """
        return self.size_spec.memory_max - self.configs.reserved_memory

    @property
    def cpu_min(self) -> float:
        """
        Minimum amount of vCPU units that is ideally suited for this fleet.

        If multiple fleets exist in the same sector, this should be the same value as
        the maximum size of the smaller fleet in the same sector.
        """
        if smaller := self.configs.get_smaller_fleet(self):
            return smaller.memory_max
        return 0

    @property
    def cpu_max(self) -> float:
        """
        Maximum vCPU units for the nodes in this fleet.

        Nothing should be scheduled in this fleet that meets or exceeds this limit.
        """
        return self.size_spec.cpu_max - self.configs.reserved_cpus

    @property
    def capacity_weight(self) -> float:
        """
        Relative scale of this fleet within its sector.

        This is used during capacity planning to repack capacity into other fleets in
        the same sector where excess capacity exists. The smallest fleet in a sector
        should have a value of 1 and larger fleets a multiple of that representing the
        relative scale of them to their peers.
        """
        smaller = self.configs.get_smaller_fleet(self)
        if not smaller:
            return 1.0

        if self.size_spec.kind == "memory":
            return self.size_spec.memory_max / smaller.size_spec.memory_max
        return self.size_spec.cpu_max / smaller.size_spec.cpu_max

    def to_dict(self) -> typing.Dict[str, typing.Any]:
        """Convert to a dictionary representation that is JSON serializable for logs."""
        return {
            "name": self.name,
            "sector": self.sector,
            "size": self.size_spec.size,
            "kind": self.size_spec.kind,
            "capacity_min": self.capacity_min,
            "memory_min": self.memory_min,
            "memory_max": self.memory_max,
            "cpu_min": self.cpu_min,
            "cpu_max": self.cpu_max,
            "capacity_weight": self.capacity_weight,
        }


@dataclasses.dataclass(frozen=True)
class FleetNode:
    """
    Data structure that describes a cluster node within an Ec2 fleet.

    If a node has no fleet, the fleet_name should be None, which indicates a node
    outside of fleet management.
    """

    name: str
    seconds_old: float
    instance_id: str
    requirements: "FleetRequirements"
    is_unblocked: bool
    state: str
    resource: typing.Optional[core_v1.Node]
    pods: typing.Dict[str, "CapacityItem"]

    @property
    def is_retirable(self) -> bool:
        """Whether or not the node is old enough to be retired."""
        grace_period = self.requirements.configs.get_inactive_grace_period()
        return self.seconds_old > grace_period


@dataclasses.dataclass(frozen=True)
class Fleet:
    """Data structure that describes an Ec2 Fleet on which to operate."""

    requirements: "FleetRequirements"
    identifier: str
    #: Current total capacity of the EC2 fleet.
    capacity: int
    #: Tags applied to the EC2 Fleet by terraform.
    tags: typing.Dict[str, str]

    @property
    def name(self) -> str:
        """Name of the fleet in the format '{sector}-{size}'."""
        return self.requirements.name

    @property
    def sector(self) -> str:
        """Sector in which the fleet resides."""
        return self.requirements.sector

    @property
    def size(self) -> str:
        """Node sizes of the fleet."""
        return self.requirements.size


@dataclasses.dataclass(frozen=True)
class CapacityItem:
    """
    Data structure that describes a Pod and its computed capacity.

    Capacity is determined based on container definition resources within it.
    """

    pod_id: str
    #: Fleet sector in which the item resides.
    sector: str
    #: An optional fleet size in which the item should be scheduled.
    size: typing.Optional[str]
    memory: int
    cpu: float
    pod: core_v1.Pod
    status: core_v1.PodStatus
    #: Whether or not the pod is allowed to be bounced from a node when
    #: excess node capacity is found. Only pods in ReplicaSets are allowed
    #: to be bounced because we want to avoid long-running deployments from
    #: clogging up excess node capacity.
    is_bouncable: bool = False
