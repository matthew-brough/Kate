from base64 import b64encode
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.k8s import LoadgenStatus, PartitionInfo, PodInfo
from app.main import CHAOS_TOKEN


def loadgen_status(
    replicas: int = 1, users: str = "5", spawn_rate: str = "1"
) -> LoadgenStatus:
    return LoadgenStatus(
        deployment_name="loadgen",
        replicas=replicas,
        ready_replicas=replicas,
        users=users,
        spawn_rate=spawn_rate,
        host="http://gateway-headless:8000",
    )


@patch("app.main.k8s")
def test_index(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.list_pods.return_value = []
    mock_k8s.list_partitions.return_value = []
    mock_k8s.get_loadgen_status.return_value = loadgen_status()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Chaos Portal" in resp.text
    assert "platform" in resp.text
    assert "Loadgen Demand" in resp.text
    assert "baseline: 1 pods / 5 users each" in resp.text


@patch("app.main.k8s")
def test_pod_list(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.list_pods.return_value = [
        PodInfo(name="orders-api-abc123", phase="Running", ready="1/1", node="k3d-agent-0"),
        PodInfo(name="gateway-xyz789", phase="Pending", ready="0/1", node="-"),
    ]
    resp = client.get("/pods")
    assert resp.status_code == 200
    assert "orders-api-abc123" in resp.text
    assert "Running" in resp.text
    assert "gateway-xyz789" in resp.text
    assert "Pending" in resp.text


@pytest.mark.parametrize(
    "pod_name",
    [
        "orders-api-fb4d9f8dc-7nfhn",
        "gateway-5dc77c9bb8-7wq22",
        "loadgen-6bff8fc46f-fz67l",
        "redis-master-698b5f9799-rb6wg",
    ],
)
@patch("app.main.k8s")
def test_kill_pod(mock_k8s: MagicMock, client: TestClient, pod_name: str) -> None:
    mock_k8s.delete_pod.return_value = None
    mock_k8s.list_pods.return_value = []
    resp = client.post(f"/pods/{pod_name}/kill")
    assert resp.status_code == 200
    mock_k8s.delete_pod.assert_called_once_with("platform", pod_name)


@patch("app.main.k8s")
def test_pod_list_marks_unconfigured_pods_protected(
    mock_k8s: MagicMock, client: TestClient
) -> None:
    mock_k8s.list_pods.return_value = [
        PodInfo(
            name="redis-master-698b5f9799-rb6wg",
            phase="Running",
            ready="1/1",
            node="k3d-agent-0",
        ),
        PodInfo(
            name="auth-api-postgresql-86985b8c8c-dt9pq",
            phase="Running",
            ready="1/1",
            node="k3d-agent-0",
        ),
        PodInfo(
            name="chaos-portal-74969847f5-6vn6n",
            phase="Running",
            ready="1/1",
            node="k3d-agent-0",
        ),
    ]
    resp = client.get("/pods")
    assert resp.status_code == 200
    assert "/pods/redis-master-698b5f9799-rb6wg/kill" in resp.text
    assert "/pods/auth-api-postgresql-86985b8c8c-dt9pq/kill" not in resp.text
    assert "/pods/chaos-portal-74969847f5-6vn6n/kill" not in resp.text
    assert resp.text.count("protected") == 2


@patch("app.main.k8s")
def test_partition_list(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.list_partitions.return_value = [
        PartitionInfo(service="orders-api", policy_name="orders-api-allow-ingress")
    ]
    resp = client.get("/partitions")
    assert resp.status_code == 200
    assert "PARTITIONED" in resp.text
    assert "orders-api" in resp.text


@patch("app.main.k8s")
def test_toggle_partition_apply(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.toggle_partition.return_value = True
    mock_k8s.list_partitions.return_value = [
        PartitionInfo(service="orders-api", policy_name="orders-api-allow-ingress")
    ]
    resp = client.post("/partitions/orders-api/toggle")
    assert resp.status_code == 200
    mock_k8s.toggle_partition.assert_called_once_with("platform", "orders-api")
    assert "PARTITIONED" in resp.text


@patch("app.main.k8s")
def test_toggle_partition_restore(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.toggle_partition.return_value = False
    mock_k8s.list_partitions.return_value = []
    resp = client.post("/partitions/orders-api/toggle")
    assert resp.status_code == 200
    assert "PARTITIONED" not in resp.text


@patch("app.main.k8s")
def test_loadgen_panel(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.get_loadgen_status.return_value = loadgen_status(
        replicas=3, users="100", spawn_rate="20"
    )
    resp = client.get("/loadgen")
    assert resp.status_code == 200
    assert "loadgen" in resp.text
    assert "3/3" in resp.text
    assert "surge: 3 pods / 100 users each" in resp.text


@patch("app.main.k8s")
def test_apply_loadgen_profile(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.get_loadgen_status.return_value = loadgen_status(
        replicas=3, users="100", spawn_rate="20"
    )
    resp = client.post("/loadgen/surge/apply")
    assert resp.status_code == 200
    mock_k8s.scale_loadgen.assert_called_once_with(
        "platform", "loadgen", replicas=3, users=100, spawn_rate=20
    )
    assert "surge: 3 pods / 100 users each" in resp.text


@patch("app.main.k8s")
def test_apply_loadgen_profile_rejects_unknown(
    mock_k8s: MagicMock, client: TestClient
) -> None:
    resp = client.post("/loadgen/unbounded/apply")
    assert resp.status_code == 400
    assert "not configured" in resp.text
    mock_k8s.scale_loadgen.assert_not_called()


def test_health(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    assert client.get("/health").text == "ok"


def test_ready(client: TestClient) -> None:
    assert client.get("/ready").status_code == 200


@patch("app.main.k8s")
def test_kill_pod_rejects_outside_allowlist(mock_k8s: MagicMock, client: TestClient) -> None:
    resp = client.post("/pods/chaos-portal-abc123/kill")
    assert resp.status_code == 400
    assert "allowlist" in resp.text
    mock_k8s.delete_pod.assert_not_called()


@patch("app.main.k8s")
def test_toggle_partition_rejects_outside_allowlist(
    mock_k8s: MagicMock, client: TestClient
) -> None:
    resp = client.post("/partitions/gateway/toggle")
    assert resp.status_code == 400
    assert "allowlist" in resp.text
    mock_k8s.toggle_partition.assert_not_called()


def test_unauth_request_rejected(unauth_client: TestClient) -> None:
    """TokenAuthMiddleware: missing X-Chaos-Token → 401 on protected routes."""
    assert unauth_client.get("/").status_code == 401
    assert unauth_client.get("/pods").status_code == 401
    assert unauth_client.post("/pods/orders-api-abc/kill").status_code == 401
    assert unauth_client.post("/partitions/orders-api/toggle").status_code == 401


def test_wrong_token_rejected(unauth_client: TestClient) -> None:
    unauth_client.headers["X-Chaos-Token"] = "not-the-right-token"
    assert unauth_client.get("/").status_code == 401


def test_malformed_basic_auth_rejected(unauth_client: TestClient) -> None:
    unauth_client.headers["Authorization"] = "Basic not-base64"
    assert unauth_client.get("/").status_code == 401


@patch("app.main.k8s")
def test_basic_auth_allows_browser_access(mock_k8s: MagicMock, unauth_client: TestClient) -> None:
    mock_k8s.list_pods.return_value = []
    mock_k8s.list_partitions.return_value = []
    credentials = b64encode(f"chaos:{CHAOS_TOKEN}".encode()).decode()
    unauth_client.headers["Authorization"] = f"Basic {credentials}"
    assert unauth_client.get("/").status_code == 200


@patch("app.main.k8s")
def test_bearer_auth_allowed(mock_k8s: MagicMock, unauth_client: TestClient) -> None:
    mock_k8s.list_pods.return_value = []
    mock_k8s.list_partitions.return_value = []
    unauth_client.headers["Authorization"] = f"Bearer {CHAOS_TOKEN}"
    assert unauth_client.get("/").status_code == 200


@patch("app.main.k8s")
def test_dev_auth_mode_allows_browser_access(
    mock_k8s: MagicMock, unauth_client: TestClient, monkeypatch
) -> None:
    mock_k8s.list_pods.return_value = []
    mock_k8s.list_partitions.return_value = []
    monkeypatch.setattr("app.main.CHAOS_AUTH_MODE", "dev")
    assert unauth_client.get("/").status_code == 200


def test_health_endpoints_open(unauth_client: TestClient) -> None:
    """/health and /ready bypass TokenAuthMiddleware so kubelet probes work."""
    assert unauth_client.get("/health").status_code == 200
    assert unauth_client.get("/ready").status_code == 200
