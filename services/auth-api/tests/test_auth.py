import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import User

VALID_PASSWORD = "Str0ng!Passxx"


async def test_register_creates_user(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"username": "Alice", "email": "Alice@Example.com", "password": VALID_PASSWORD},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert "id" in body
    assert "password_hash" not in body


async def test_register_duplicate_returns_409(client: AsyncClient) -> None:
    payload = {"username": "bob", "email": "bob@example.com", "password": VALID_PASSWORD}
    await client.post("/auth/register", json=payload)
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_duplicate_skips_password_hash(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = {"username": "bob", "email": "bob@example.com", "password": VALID_PASSWORD}
    await client.post("/auth/register", json=payload)

    async def fail_hash(password: str) -> str:
        raise AssertionError("duplicate registration should not hash password")

    monkeypatch.setattr("app.routers.auth.hash_password_async", fail_hash)
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 409


async def test_register_case_variant_duplicate_returns_409(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": VALID_PASSWORD},
    )
    r = await client.post(
        "/auth/register",
        json={"username": "BOB", "email": "other@example.com", "password": VALID_PASSWORD},
    )
    assert r.status_code == 409


async def test_register_short_password_returns_422(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "short"},
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "password",
    [
        "lowercase123!",
        "UPPERCASE123!",
        "NoDigitsHere!",
        "NoSymbols1234",
        "carol123!Pass",
        "prefixcarol123!Pass",
    ],
)
async def test_register_password_policy_returns_422(
    client: AsyncClient, password: str
) -> None:
    r = await client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": password},
    )
    assert r.status_code == 422


async def test_token_returns_bearer(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": VALID_PASSWORD},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "DAVE", "password": VALID_PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 10


async def test_token_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post(
        "/auth/register",
        json={"username": "eve", "email": "eve@example.com", "password": VALID_PASSWORD},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "eve", "password": "wrongpassword"},
    )
    assert r.status_code == 401


async def test_failed_logins_lock_account(
    client: AsyncClient, test_engine: AsyncEngine
) -> None:
    await client.post(
        "/auth/register",
        json={"username": "frank", "email": "frank@example.com", "password": VALID_PASSWORD},
    )

    for _ in range(5):
        r = await client.post(
            "/auth/token",
            data={"username": "frank", "password": "wrongpassword"},
        )
        assert r.status_code == 401

    locked = await client.post(
        "/auth/token",
        data={"username": "frank", "password": VALID_PASSWORD},
    )
    assert locked.status_code == 401

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "frank"))
        user = result.scalar_one()
        assert user.failed_login_attempts == 5
        assert user.locked_until is not None
        assert user.last_failed_login_at is not None


async def test_successful_login_resets_failed_attempts(
    client: AsyncClient, test_engine: AsyncEngine
) -> None:
    await client.post(
        "/auth/register",
        json={"username": "grace", "email": "grace@example.com", "password": VALID_PASSWORD},
    )
    await client.post(
        "/auth/token",
        data={"username": "grace", "password": "wrongpassword"},
    )
    r = await client.post(
        "/auth/token",
        data={"username": "grace", "password": VALID_PASSWORD},
    )
    assert r.status_code == 200

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "grace"))
        user = result.scalar_one()
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


async def test_token_unknown_user_returns_401(client: AsyncClient) -> None:
    r = await client.post(
        "/auth/token",
        data={"username": "ghost", "password": VALID_PASSWORD},
    )
    assert r.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"username": "x", "email": "x@example.com"},  # missing password
        {"username": "x", "password": VALID_PASSWORD},  # missing email
        {"email": "x@example.com", "password": VALID_PASSWORD},  # missing username
    ],
)
async def test_register_missing_fields(client: AsyncClient, payload: dict[str, str]) -> None:
    r = await client.post("/auth/register", json=payload)
    assert r.status_code == 422
