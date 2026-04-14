from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "template-service"


async def test_ready_ok(client: AsyncClient) -> None:
    r = await client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


async def test_metrics_exposed(client: AsyncClient) -> None:
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert b"http_requests_total" in r.content
