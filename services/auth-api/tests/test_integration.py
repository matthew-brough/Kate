"""
Integration tests — require Docker (INTEGRATION=1).

Verifies registration, duplicate-user rejection, and JWT minting against a real
Postgres container.
"""

import os
from collections.abc import AsyncGenerator, Generator

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

VALID_PASSWORD = "Str0ng!Passxx"

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="set INTEGRATION=1 to run integration tests (requires Docker)",
)


@pytest.fixture(scope="module")
def pg_database_url() -> Generator[str]:
    if database_url := os.getenv("INTEGRATION_DATABASE_URL"):
        yield database_url
        return

    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")


@pytest.fixture
async def pg_engine(pg_database_url: str) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(pg_database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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

    async with AsyncClient(transport=ASGITransport(app=instance), base_url="http://test") as c:
        yield c

    instance.dependency_overrides.clear()
    _db_module.engine = original


async def test_pg_register_and_login(pg_client: AsyncClient) -> None:
    r = await pg_client.post(
        "/auth/register",
        json={"username": "Integ", "email": "Integ@Example.com", "password": VALID_PASSWORD},
    )
    assert r.status_code == 201

    r = await pg_client.post(
        "/auth/token",
        data={"username": "integ", "password": VALID_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert token


async def test_pg_duplicate_email_rejected(pg_client: AsyncClient) -> None:
    payload = {"username": "dupuser", "email": "dup@example.com", "password": VALID_PASSWORD}
    await pg_client.post("/auth/register", json=payload)
    r = await pg_client.post("/auth/register", json=payload)
    assert r.status_code == 409


async def test_pg_wrong_password_rejected(pg_client: AsyncClient) -> None:
    await pg_client.post(
        "/auth/register",
        json={"username": "wronguser", "email": "wrong@example.com", "password": VALID_PASSWORD},
    )
    r = await pg_client.post(
        "/auth/token",
        data={"username": "wronguser", "password": "incorrect"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 401
