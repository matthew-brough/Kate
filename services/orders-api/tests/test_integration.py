"""
Integration tests — require Docker (INTEGRATION=1).

Spin up a real Postgres container via testcontainers, run the full ASGI app against it,
and assert end-to-end DB behaviour that SQLite in-memory tests cannot cover (e.g. NUMERIC
precision, index-backed queries).
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

pytestmark = pytest.mark.skipif(
    not os.getenv("INTEGRATION"),
    reason="set INTEGRATION=1 to run integration tests (requires Docker)",
)

_USER_ID = "user-integ-001"
_ORDER = {
    "product_id": "prod-integ-abc",
    "quantity": 5,
    "unit_price": 12.50,
}


@pytest.fixture(scope="module")
def pg_database_url() -> Generator[str]:
    if database_url := os.getenv("INTEGRATION_DATABASE_URL"):
        yield database_url
        return

    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )


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

    async with AsyncClient(
        transport=ASGITransport(app=instance),
        base_url="http://test",
        headers={"X-User-Id": _USER_ID},
    ) as c:
        yield c

    instance.dependency_overrides.clear()
    _db_module.engine = original


async def test_pg_create_and_list(pg_client: AsyncClient) -> None:
    r = await pg_client.post("/orders", json=_ORDER)
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await pg_client.get("/orders")
    assert r.status_code == 200
    assert any(o["id"] == order_id for o in r.json())


async def test_pg_get_by_id(pg_client: AsyncClient) -> None:
    created = (await pg_client.post("/orders", json=_ORDER)).json()
    r = await pg_client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json()["product_id"] == _ORDER["product_id"]


async def test_pg_status_transition(pg_client: AsyncClient) -> None:
    created = (await pg_client.post("/orders", json=_ORDER)).json()
    r = await pg_client.patch(f"/orders/{created['id']}", json={"status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_pg_unit_price_precision(pg_client: AsyncClient) -> None:
    payload = {**_ORDER, "unit_price": 9.99}
    created = (await pg_client.post("/orders", json=payload)).json()
    r = await pg_client.get(f"/orders/{created['id']}")
    assert r.json()["unit_price"] == 9.99
    assert isinstance(r.json()["unit_price"], float)
