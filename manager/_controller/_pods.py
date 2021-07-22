import datetime
import typing

from kuber.latest import core_v1
from kuber.latest import meta_v1

from manager import _conversions
from manager import _types


def _get_last_transition_time(pod: core_v1.Pod) -> float:
    """Get the timestamp the last transition time of the pod as a unix timestamp."""
    transition_times = [
        datetime.datetime.fromisoformat(
            c.last_transition_time.replace("Z", "")
        ).timestamp()
        for c in (pod.status.conditions or [])
    ]
    return max([0, *transition_times])


def _has_compatible_selector(pod: core_v1.Pod) -> bool:
    """Determine if the pod has kluster-fleet-manager-compatible node selectors."""
    with pod.spec as s:
        return bool(
            s.node_selector
            and next(
                (True for key in ["sector", "fleet", "size"] if key in s.node_selector),
                False,
            )
        )


def _is_blocking_pod(pod: core_v1.Pod, inactive_grace_period: int = 0) -> bool:
    """
    Determine if the specified pod should be considered in fleet capacity allocation.

    A number of criteria will disqualify a pod from being considered for scalable fleet
    capacity.
    """
    now = datetime.datetime.utcnow().timestamp()
    recently = now - inactive_grace_period
    last_transition_time = _get_last_transition_time(pod)
    recently_transitioned = last_transition_time >= recently
    has_compatible_selector = _has_compatible_selector(pod)

    owner_kinds = [ref.kind for ref in (pod.metadata.owner_references or [])]
    return (
        # Anything in the `kube-system` namespace is running on the control
        # plane and should be ignored unless it has a kluster-fleet-manager-compatible
        # node selector, which is the case for add-ons like the metrics server that
        # reside in the kube-system namespace but are not part of the EKS control plane.
        (pod.metadata.namespace != "kube-system" or has_compatible_selector)
        # DaemonSets run on every node and should be included in
        # considerations for scaling capacity.
        and "DaemonSet" not in owner_kinds
        # Pods in the running or pending states should block as well as pods
        # that have recently transitioned if the grace period is set.
        and (
            pod.status.phase.lower() in ("running", "pending")
            or (inactive_grace_period > 0 and recently_transitioned)
        )
    )


def _is_bouncable_pod(pod: core_v1.Pod, running_grace_period: int = 1800) -> bool:
    """Determine if the specified pod could be rescheduled on a different node."""
    now = datetime.datetime.utcnow().timestamp()
    recently = now - running_grace_period
    recently_transitioned = _get_last_transition_time(pod) >= recently
    has_compatible_selector = _has_compatible_selector(pod)

    owners = pod.metadata.owner_references or []
    controller: typing.Optional[meta_v1.OwnerReference] = next(
        (ref for ref in owners if ref.controller), None
    )
    return (
        # Anything in the `kube-system` namespace is running on the control
        # plane and should be ignored unless it has a kluster-fleet-manager-compatible
        # node selector, which is the case for add-ons like the metrics server that
        # reside in the kube-system namespace but are not part of the EKS control plane.
        (pod.metadata.namespace != "kube-system" or has_compatible_selector)
        # Only allow bouncing pods inside a ReplicaSet that will be rescheduled
        # by that ReplicaSet when bounced.
        and controller is not None
        and controller.kind == "ReplicaSet"
        # Only running pods should be bouncable.
        and pod.status.phase.lower() == "running"
        # Don't bounce pods that have recently transitioned into a
        # running state.
        and not recently_transitioned
    )


def _to_capacity_item(
    configs: "_types.ManagerConfigs",
    pod: core_v1.Pod,
) -> "_types.CapacityItem":
    """
    Convert a pod object into a CapacityItem data structure.

    This is done by determining how many resources are needed collectively by the pod
    based on the configuration of its containers.

    :param pod:
        The pod object to convert into its equivalent capacity item.
    """
    memory: float = 0.0
    cpus: float = 0.0
    for c in pod.spec.containers:
        values = {**(c.resources.requests or {}), **(c.resources.limits or {})}
        memory += float(_conversions.to_bytes(values.get("memory") or "0"))
        cpus += _conversions.to_cpus(values.get("cpu") or "0")

    node_selector = pod.spec.node_selector or {}

    if fleet := node_selector.get("fleet"):
        sector, size = fleet.split("-", 1)
    else:
        sector = node_selector.get("sector", configs.default_fleet_sector)
        size = node_selector.get("size")

    return _types.CapacityItem(
        pod_id=f"{pod.metadata.namespace}:{pod.metadata.name}",
        sector=sector,
        size=size,
        memory=int((1 + configs.default_over_subscription) * memory),
        cpu=(1 + configs.default_over_subscription) * cpus,
        pod=pod,
        status=pod.status,
        is_bouncable=_is_bouncable_pod(pod),
    )


def get_pods(
    configs: "_types.ManagerConfigs",
    inactive_grace_period: int = None,
) -> typing.List["_types.CapacityItem"]:
    """
    Create a list of pods in the cluster that contribute to capacity.

    See the `is_blocking_pod` function for how pods can be disqualified from being
    fleet pods considered for capacity.
    """
    api = core_v1.Pod.get_resource_api()
    all_pods = [
        core_v1.Pod().from_dict(pod.to_dict())
        for pod in api.list_pod_for_all_namespaces().items
    ]

    grace_period = inactive_grace_period or configs.get_inactive_grace_period()
    return [
        _to_capacity_item(configs, p)
        for p in all_pods
        if _is_blocking_pod(p, grace_period)
    ]
