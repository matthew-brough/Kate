import gzip

import httpx
import respx
from httpx import AsyncClient
from pytest import MonkeyPatch

from app.settings import settings


async def test_health(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_ready(client: AsyncClient) -> None:
    r = await client.get("/ready")
    assert r.status_code == 200


async def test_metrics(client: AsyncClient) -> None:
    r = await client.get("/metrics")
    assert r.status_code == 200


async def test_orders_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/orders")
    assert r.status_code == 401


async def test_orders_bad_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/orders", headers={"Authorization": "Bearer bad-token"})
    assert r.status_code == 401


async def test_reports_no_auth_returns_401(client: AsyncClient) -> None:
    r = await client.get("/api/reports")
    assert r.status_code == 401


async def test_auth_route_proxied_without_auth(
    client: AsyncClient, mock_upstream: respx.MockRouter
) -> None:
    mock_upstream.post("http://auth-api:8000/auth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "token_type": "bearer"})
    )
    r = await client.post(
        "/api/auth/token",
        data={"username": "alice", "password": "secret"},
    )
    assert r.status_code == 200


async def test_auth_token_rate_limit_uses_x_forwarded_for_when_trusted(
    client: AsyncClient,
    mock_upstream: respx.MockRouter,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rate_limit_trust_x_forwarded_for", True)
    mock_upstream.post("http://auth-api:8000/auth/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "token_type": "bearer"})
    )

    for _ in range(10):
        r = await client.post(
            "/api/auth/token",
            data={"username": "alice", "password": "secret"},
            headers={"X-Forwarded-For": "198.51.100.1, 10.0.0.10"},
        )
        assert r.status_code == 200

    limited = await client.post(
        "/api/auth/token",
        data={"username": "alice", "password": "secret"},
        headers={"X-Forwarded-For": "198.51.100.1, 10.0.0.10"},
    )
    assert limited.status_code == 429

    other_client = await client.post(
        "/api/auth/token",
        data={"username": "alice", "password": "secret"},
        headers={"X-Forwarded-For": "198.51.100.2, 10.0.0.10"},
    )
    assert other_client.status_code == 200


async def test_orders_proxied_with_valid_token(
    client: AsyncClient,
    valid_token: str,
    mock_upstream: respx.MockRouter,
) -> None:
    mock_upstream.get("http://orders-api:8000/orders").mock(
        return_value=httpx.Response(200, json=[])
    )
    r = await client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r.status_code == 200


async def test_proxy_strips_unsafe_upstream_response_headers(
    client: AsyncClient,
    valid_token: str,
    mock_upstream: respx.MockRouter,
) -> None:
    mock_upstream.get("http://orders-api:8000/orders").mock(
        return_value=httpx.Response(
            200,
            content=gzip.compress(b"[]"),
            headers={
                "Connection": "keep-alive",
                "Content-Encoding": "gzip",
                "Content-Length": "999",
                "Transfer-Encoding": "chunked",
                "X-Upstream-Trace": "trace-1",
            },
        )
    )
    r = await client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {valid_token}"},
    )

    assert r.status_code == 200
    assert r.headers["content-length"] == "2"
    assert "connection" not in r.headers
    assert "content-encoding" not in r.headers
    assert "transfer-encoding" not in r.headers
    assert r.headers["x-upstream-trace"] == "trace-1"


async def test_upstream_unavailable_returns_503(
    client: AsyncClient,
    valid_token: str,
    mock_upstream: respx.MockRouter,
) -> None:
    mock_upstream.get("http://orders-api:8000/orders").mock(
        side_effect=httpx.ConnectError("refused")
    )
    r = await client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert r.status_code == 503
