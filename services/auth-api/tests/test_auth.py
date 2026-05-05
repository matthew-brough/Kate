import pytest
from httpx import AsyncClient


async def test_register_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret123"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert "id" in body
    assert "password_hash" not in body


async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    payload = {"username": "bob", "email": "bob@example.com", "password": "secret123"}
    await client.post("/auth/register", json=payload)
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_short_password_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "short"},
    )
    assert r.status_code == 422


async def test_token_returns_bearer(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "secret123"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "dave", "password": "secret123"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


async def test_token_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "eve", "email": "eve@example.com", "password": "secret123"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "eve", "password": "wrongpassword"},
    )
    assert r.status_code == 401


async def test_token_unknown_user_returns_401(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/token",
        data={"username": "ghost", "password": "secret123"},
    )
    assert r.status_code == 401


async def test_verify_valid_token(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "frank", "email": "frank@example.com", "password": "secret123"},
    )
    token_r = await client.post(
        "/auth/token",
        data={"username": "frank", "password": "secret123"},
    )
    token = token_r.json()["access_token"]
    r = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "frank"


async def test_verify_invalid_token_returns_401(client: AsyncClient) -> None:
    r = await client.get("/auth/verify", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "x", "email": "x@example.com"},  # missing password
        {"username": "x", "password": "secret123"},  # missing email
        {"email": "x@example.com", "password": "secret123"},  # missing username
    ],
)
async def test_register_missing_fields(client: AsyncClient, payload: dict[str, str]) -> None:
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 422
