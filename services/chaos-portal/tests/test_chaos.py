from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from app.k8s import PartitionInfo, PodInfo


@patch("app.main.k8s")
def test_index(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.list_pods.return_value = []
    mock_k8s.list_partitions.return_value = []
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Chaos Portal" in resp.text
    assert "platform" in resp.text


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


@patch("app.main.k8s")
def test_kill_pod(mock_k8s: MagicMock, client: TestClient) -> None:
    mock_k8s.delete_pod.return_value = None
    mock_k8s.list_pods.return_value = []
    resp = client.post("/pods/orders-api-abc123/kill")
    assert resp.status_code == 200
    mock_k8s.delete_pod.assert_called_once_with("platform", "orders-api-abc123")


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


def test_health_endpoints_open(unauth_client: TestClient) -> None:
    """/health and /ready bypass TokenAuthMiddleware so kubelet probes work."""
    assert unauth_client.get("/health").status_code == 200
    assert unauth_client.get("/ready").status_code == 200
