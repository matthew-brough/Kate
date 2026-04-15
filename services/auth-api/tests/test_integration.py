"""
Integration tests — require Docker (INTEGRATION=1).

Verifies registration, duplicate-user rejection, JWT minting, and /verify round-trip
against a real Postgres container.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.db as _db_module
from app.db import Base, get_session
from app.main import create_app

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="set INTEGRATION=1 to run integration tests (requires Docker)",
)


@pytest.fixture(scope="module")
async def pg_engine() -> AsyncGenerator[AsyncEngine]:
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()


@pytest.fixture
async def pg_client(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncClient]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        pg_engine, expire_on_commit=False
    )

    async def _get_session() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    original = _db_module.engine
    _db_module.engine = pg_engine
    instance = create_app()
    instance.dependency_overrides[get_session] = _get_session

    async with AsyncClient(
        transport=ASGITransport(app=instance), base_url="http://test"
    ) as c:
        yield c

    instance.dependency_overrides.clear()
    _db_module.engine = original


async def test_pg_register_and_login(pg_client: AsyncClient) -> None:
    r = await pg_client.post(
        "/register", json={"email": "integ@example.com", "password": "s3cret!"}
    )
    assert r.status_code == 201

    r = await pg_client.post(
        "/token",
        data={"username": "integ@example.com", "password": "s3cret!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token


async def test_pg_duplicate_email_rejected(pg_client: AsyncClient) -> None:
    payload = {"email": "dup@example.com", "password": "pass1234"}
    await pg_client.post("/register", json=payload)
    r = await pg_client.post("/register", json=payload)
    assert r.status_code == 409


async def test_pg_verify_token(pg_client: AsyncClient) -> None:
    await pg_client.post(
        "/register", json={"email": "verify@example.com", "password": "pass1234"}
    )
    token_r = await pg_client.post(
        "/token",
        data={"username": "verify@example.com", "password": "pass1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = token_r.json()["access_token"]

    r = await pg_client.get(
        "/verify", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json()["email"] == "verify@example.com"


async def test_pg_wrong_password_rejected(pg_client: AsyncClient) -> None:
    await pg_client.post(
        "/register", json={"email": "wrong@example.com", "password": "correct"}
    )
    r = await pg_client.post(
        "/token",
        data={"username": "wrong@example.com", "password": "incorrect"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401
