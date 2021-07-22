import typing

from manager import _types


def _to_fleet(
    fleet_requirements: "_types.FleetRequirements",
    fleet_data: dict,
) -> "_types.Fleet":
    """
    Convert a boto3 describe fleet object into a Fleet data structure.

    This simplifies the information from the raw fleet data for use
    elsewhere within this application.
    """
    fleet_id = fleet_data["FleetId"]
    tags = {t["Key"]: t["Value"] for t in fleet_data["Tags"]}
    capacity = fleet_data["TargetCapacitySpecification"]["TotalTargetCapacity"]
    return _types.Fleet(
        requirements=fleet_requirements,
        identifier=fleet_id,
        capacity=capacity,
        tags=tags,
    )


def get_fleet(
    configs: "_types.ManagerConfigs",
    fleet_requirements: "_types.FleetRequirements",
) -> typing.Optional["_types.Fleet"]:
    """
    Fetch fleet status for the specified fleet.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet_requirements:
        Requirements definition for the fleet of interest.
    """
    client = configs.session.client("ec2")
    response = client.describe_fleets(
        Filters=[
            {"Name": "fleet-state", "Values": ["submitted", "active", "modifying"]},
            {"Name": "tag:cluster", "Values": [configs.cluster_name]},
            {"Name": "tag:fleet", "Values": [fleet_requirements.name]},
        ]
    )
    return next((_to_fleet(fleet_requirements, f) for f in response["Fleets"]), None)


def adjust_fleet(
    configs: "_types.ManagerConfigs",
    fleet: "_types.Fleet",
    target_capacity: int,
) -> bool:
    """
    Carry out a fleet adjustment action to change the target capacity of the fleet.

    :param configs:
        Current execution configuration for the kluster fleet manager.
    :param fleet:
        Fleet object on which to adjust capacity.
    :param target_capacity:
        Number of nodes to set the capacity to for the specified fleet.
    :return:
        Whether or not the capacity change was successfully assigned or not.
    """
    client = configs.session.client("ec2")
    response = client.modify_fleet(
        FleetId=fleet.identifier,
        TargetCapacitySpecification={
            "TotalTargetCapacity": target_capacity,
        },
    )
    return response.get("Return") or False
