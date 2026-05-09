import json
import logging
from dataclasses import dataclass
from typing import Any

from kubernetes import client, config
from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)

_configured: bool = False


def _ensure_config() -> None:
    global _configured
    if _configured:
        return
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    _configured = True


def _core() -> client.CoreV1Api:
    _ensure_config()
    return client.CoreV1Api()


def _networking() -> client.NetworkingV1Api:
    _ensure_config()
    return client.NetworkingV1Api()


def _apps() -> client.AppsV1Api:
    _ensure_config()
    return client.AppsV1Api()


@dataclass
class PodInfo:
    name: str
    phase: str
    ready: str
    node: str


@dataclass
class PartitionInfo:
    service: str
    policy_name: str


@dataclass
class LoadgenStatus:
    deployment_name: str
    replicas: int
    ready_replicas: int
    users: str
    spawn_rate: str
    host: str


def list_pods(namespace: str) -> list[PodInfo]:
    pods = _core().list_namespaced_pod(namespace=namespace)
    result: list[PodInfo] = []
    for pod in pods.items:
        meta = pod.metadata
        status = pod.status
        spec = pod.spec
        if meta is None or status is None or spec is None or meta.name is None:
            continue
        statuses = status.container_statuses or []
        ready_count = sum(1 for s in statuses if s.ready)
        result.append(
            PodInfo(
                name=meta.name,
                phase=status.phase or "Unknown",
                ready=f"{ready_count}/{len(statuses)}",
                node=spec.node_name or "-",
            )
        )
    return sorted(result, key=lambda p: p.name)


def delete_pod(namespace: str, name: str) -> None:
    _core().delete_namespaced_pod(name=name, namespace=namespace)


def list_partitions(namespace: str) -> list[PartitionInfo]:
    policies = _networking().list_namespaced_network_policy(namespace=namespace)
    result: list[PartitionInfo] = []
    for policy in policies.items:
        meta = policy.metadata
        if meta is None or meta.name is None:
            continue
        annotations = meta.annotations or {}
        if annotations.get("chaos.kate.dev/partition-active") == "true":
            service = (meta.labels or {}).get("chaos.kate.dev/service", meta.name)
            result.append(PartitionInfo(service=service, policy_name=meta.name))
    return result


def toggle_partition(namespace: str, service: str) -> bool:
    """
    Patches the allow-ingress NetworkPolicy for `service`.

    Partition: stores current ingress rules in an annotation, then sets ingress=[].
    Un-partition: restores ingress rules from annotation.

    Returns True if partition is now active, False if restored.
    """
    policy_name = f"{service}-allow-ingress"
    try:
        policy = _networking().read_namespaced_network_policy(name=policy_name, namespace=namespace)
    except ApiException as e:
        if e.status == 404:
            raise ValueError(
                f"NetworkPolicy {policy_name!r} not found in namespace {namespace!r}. "
                "Ensure networkPolicy.enabled=true in dev-values.yaml for this service."
            ) from e
        raise

    if policy.metadata is None or policy.spec is None:
        raise ValueError(
            f"NetworkPolicy {policy_name!r} returned without metadata/spec from API server."
        )
    annotations = policy.metadata.annotations or {}

    if annotations.get("chaos.kate.dev/partition-active") == "true":
        original = json.loads(annotations.get("chaos.kate.dev/original-ingress", "[]"))
        patch: dict[str, Any] = {
            "metadata": {
                "annotations": {
                    "chaos.kate.dev/partition-active": None,
                    "chaos.kate.dev/original-ingress": None,
                    "chaos.kate.dev/service": None,
                },
                "labels": {"chaos.kate.dev/service": None},
            },
            "spec": {"ingress": original},
        }
        _networking().patch_namespaced_network_policy(
            name=policy_name, namespace=namespace, body=patch
        )
        return False
    else:
        api_client = ApiClient()
        ingress_rules = [
            api_client.sanitize_for_serialization(r) for r in (policy.spec.ingress or [])
        ]
        patch: dict[str, Any] = {
            "metadata": {
                "annotations": {
                    "chaos.kate.dev/partition-active": "true",
                    "chaos.kate.dev/original-ingress": json.dumps(ingress_rules),
                },
                "labels": {"chaos.kate.dev/service": service},
            },
            "spec": {"ingress": []},
        }
        _networking().patch_namespaced_network_policy(
            name=policy_name, namespace=namespace, body=patch
        )
        return True


def get_loadgen_status(namespace: str, deployment_name: str) -> LoadgenStatus:
    deployment = _apps().read_namespaced_deployment(name=deployment_name, namespace=namespace)
    spec = deployment.spec
    status = deployment.status
    containers = spec.template.spec.containers if spec and spec.template.spec else []
    container = next(
        (c for c in containers if c.name == "loadgen"),
        containers[0] if containers else None,
    )
    env_items = container.env or [] if container else []
    env = {item.name: item.value or "" for item in env_items if item.name}
    return LoadgenStatus(
        deployment_name=deployment_name,
        replicas=spec.replicas if spec and spec.replicas is not None else 0,
        ready_replicas=status.ready_replicas if status and status.ready_replicas is not None else 0,
        users=env.get("LOCUST_USERS", "-") or "-",
        spawn_rate=env.get("LOCUST_SPAWN_RATE", "-") or "-",
        host=env.get("LOCUST_HOST", "-") or "-",
    )


def scale_loadgen(
    namespace: str,
    deployment_name: str,
    *,
    replicas: int,
    users: int,
    spawn_rate: int,
) -> None:
    patch: dict[str, Any] = {
        "spec": {
            "replicas": replicas,
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": "loadgen",
                            "env": [
                                {"name": "LOCUST_USERS", "value": str(users)},
                                {"name": "LOCUST_SPAWN_RATE", "value": str(spawn_rate)},
                            ],
                        }
                    ]
                }
            },
        }
    }
    _apps().patch_namespaced_deployment(name=deployment_name, namespace=namespace, body=patch)
