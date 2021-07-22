import datetime

from kuber.latest import core_v1
from kuber.latest import meta_v1
from pytest import mark

from manager._controller import _pods

BOUNCABLE_POD = core_v1.Pod()
with BOUNCABLE_POD as p:
    p.metadata.name = "bouncable"
    p.status.phase = "Running"
    p.status.conditions.append(
        core_v1.PodCondition(last_transition_time="2018-01-01T00:00:00Z")
    )
    p.metadata.owner_references.append(
        meta_v1.OwnerReference(kind="ReplicaSet", controller=True)
    )

NON_DEPLOYMENT_POD = core_v1.Pod().from_dict(BOUNCABLE_POD.to_dict())
NON_DEPLOYMENT_POD.metadata.owner_references = []

STOPPED_POD = core_v1.Pod().from_dict(BOUNCABLE_POD.to_dict())
STOPPED_POD.status.phase = "Complete"

SYSTEM_POD = core_v1.Pod().from_dict(BOUNCABLE_POD.to_dict())
SYSTEM_POD.metadata.namespace = "kube-system"

RECENTLY_STARTED_POD = core_v1.Pod().from_dict(BOUNCABLE_POD.to_dict())
RECENTLY_STARTED_POD.status.conditions = [
    core_v1.PodCondition(last_transition_time=datetime.datetime.utcnow().isoformat("T"))
]

SCENARIOS = (
    (BOUNCABLE_POD, True),
    (NON_DEPLOYMENT_POD, False),
    (STOPPED_POD, False),
    (SYSTEM_POD, False),
    (RECENTLY_STARTED_POD, False),
)


@mark.parametrize("pod, expected", SCENARIOS)
def test_is_bouncable_pod(pod: core_v1.Pod, expected: bool):
    """Should return expected bouncable result for each scenario."""
    result = _pods._is_bouncable_pod(pod)
    assert expected == result
