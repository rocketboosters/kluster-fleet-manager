from unittest.mock import MagicMock
from unittest.mock import patch

import lobotomy
from kuber.latest import core_v1

from manager import _configs
from manager import _controller
from manager import _types


def _create_node(
    name: str,
    fleet: str,
):
    """Creates a node for mocked testing."""
    node = core_v1.Node()
    with node.metadata as md:
        md.name = name
        md.labels.update(fleet=fleet)
        md.creation_timestamp = "2018-01-01T00:00:00Z"
    return node


@lobotomy.patch()
@patch("manager._controller.get_pods")
@patch("manager._controller._nodes.core_v1.Node.get_resource_api")
def test_get_nodes(
    get_resource_api: MagicMock,
    get_pods: MagicMock,
    lobotomized: lobotomy.Lobotomy,
):
    """..."""
    get_pods.return_value = []
    api = MagicMock()
    api.list_node.return_value = MagicMock(
        items=[_create_node("a", "primary-small"), _create_node("b", "primary-large")]
    )
    get_resource_api.return_value = api

    configs = _types.ManagerConfigs()
    configs.fleets.append(
        _types.FleetRequirements(
            configs=configs,
            sector="primary",
            size_spec=_types.SMALL_MEMORY_SPEC,
        )
    )

    fleet = _types.Fleet(configs.fleets[0], "fleet-identifier", 1, {})

    # Client for describing fleet instances that may not be in the
    # cluster at the moment.
    lobotomized.add_call(
        "ec2",
        "describe_fleet_instances",
        {"ActiveInstances": [{"InstanceId": "a"}, {"InstanceId": "c"}]},
    )
    lobotomized.add_call(
        "ec2",
        "describe_instances",
        {
            "Reservations": [
                {
                    "Instances": [
                        {"PrivateDnsName": "c", "InstanceId": "c"},
                        {"PrivateDnsName": "d", "InstanceId": "d"},
                    ]
                }
            ]
        },
    )

    nodes = _controller.get_nodes(configs, fleet)
    assert nodes["a"].requirements.size == "small"
    assert "b" not in nodes, '"b" is not in the small fleet'
    assert nodes["c"].state == _configs.WARMING_UP_STATE
    assert nodes["d"].state == _configs.WARMING_UP_STATE
