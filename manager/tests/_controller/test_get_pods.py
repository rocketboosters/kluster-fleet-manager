from unittest.mock import MagicMock
from unittest.mock import patch

from kuber.latest import core_v1

from manager import _controller
from manager import _types

BLOCKING_POD = core_v1.Pod()
with BLOCKING_POD as p:
    p.metadata.name = "blocking"
    p.metadata.namespace = "foo"
    p.status.phase = "Running"
    p.spec.node_selector.update(sector="primary", size="medium")
    p.append_container(
        name="1",
        resources=core_v1.ResourceRequirements(limits={"cpu": "1", "memory": "1Gi"}),
    )
    p.append_container(
        name="2",
        resources=core_v1.ResourceRequirements(limits={"cpu": "1", "memory": "1Gi"}),
    )

DAEMONSET_POD = core_v1.Pod()
with DAEMONSET_POD as p:
    p.metadata.name = "daemonset-pod"
    p.metadata.owner_references = [core_v1.ObjectReference(kind="DaemonSet")]
    p.status.phase = "Running"
    p.spec.node_selector.update(fleet="primary-small")


SYSTEM_POD = core_v1.Pod()
with SYSTEM_POD as pd:
    p.metadata.name = "system-pod"
    p.metadata.namespace = "kube-system"

COMPLETED_POD = core_v1.Pod()
with COMPLETED_POD as p:
    p.status.phase = "completed"


@patch("manager._controller._pods.core_v1.Pod.get_resource_api")
def test_get_pods(get_resource_api: MagicMock):
    """Should return blocking pods as capacity items."""
    api = MagicMock()
    api.list_pod_for_all_namespaces.return_value = MagicMock(
        items=[BLOCKING_POD, DAEMONSET_POD, SYSTEM_POD, COMPLETED_POD]
    )
    get_resource_api.return_value = api

    configs = _types.ManagerConfigs()

    pods = _controller.get_pods(configs)
    assert len(pods) == 1, "Expected non-blocking pods to be ignored."
    assert pods[0].pod_id == "foo:blocking"
    assert pods[0].memory > 0
    assert pods[0].cpu > 0
