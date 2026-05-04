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
