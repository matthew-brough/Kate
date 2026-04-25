from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from kubernetes import client, config  # type: ignore[import-untyped]
from kubernetes.client.exceptions import ApiException  # type: ignore[import-untyped]

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


def list_pods(namespace: str) -> list[PodInfo]:
    pods = _core().list_namespaced_pod(namespace=namespace)
    result: list[PodInfo] = []
    for pod in pods.items:
        statuses = pod.status.container_statuses or []
        ready_count = sum(1 for s in statuses if s.ready)
        result.append(PodInfo(
            name=pod.metadata.name,
            phase=pod.status.phase or "Unknown",
            ready=f"{ready_count}/{len(statuses)}",
            node=pod.spec.node_name or "-",
        ))
    return sorted(result, key=lambda p: p.name)


def delete_pod(namespace: str, name: str) -> None:
    _core().delete_namespaced_pod(name=name, namespace=namespace)


def list_partitions(namespace: str) -> list[PartitionInfo]:
    policies: Any = _networking().list_namespaced_network_policy(namespace=namespace)
    result: list[PartitionInfo] = []
    for policy in policies.items:
        annotations = policy.metadata.annotations or {}
        if annotations.get("chaos.kate.dev/partition-active") == "true":
            service = (policy.metadata.labels or {}).get(
                "chaos.kate.dev/service", policy.metadata.name
            )
            result.append(PartitionInfo(service=service, policy_name=policy.metadata.name))
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
        policy: Any = _networking().read_namespaced_network_policy(
            name=policy_name, namespace=namespace
        )
    except ApiException as e:
        if e.status == 404:
            raise ValueError(
                f"NetworkPolicy {policy_name!r} not found in namespace {namespace!r}. "
                "Ensure networkPolicy.enabled=true in dev-values.yaml for this service."
            ) from e
        raise

    annotations = policy.metadata.annotations or {}

    if annotations.get("chaos.kate.dev/partition-active") == "true":
        original = json.loads(annotations.get("chaos.kate.dev/original-ingress", "[]"))
        patch: dict = {
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
        api_client = _networking().api_client
        ingress_rules = [
            api_client.sanitize_for_serialization(r)
            for r in (policy.spec.ingress or [])
        ]
        patch = {
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
