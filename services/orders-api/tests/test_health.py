from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["service"] == "orders-api"


async def test_metrics(client: AsyncClient) -> None:
    r = await client.get("/metrics")
    assert r.status_code == 200
