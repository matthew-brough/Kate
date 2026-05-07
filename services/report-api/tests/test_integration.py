"""
Integration tests — require Docker (INTEGRATION=1).

Verifies report creation, persistence, and polling against a real Postgres container.
Celery task dispatch is mocked — the worker is an independent process and is not
spun up here; the integration boundary is the DB, not the queue.
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

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

_USER_ID = "user-integ"


@pytest.fixture(scope="module")
async def pg_engine() -> AsyncGenerator[AsyncEngine]:
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql+asyncpg://")
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
        transport=ASGITransport(app=instance),
        base_url="http://test",
        headers={"X-User-Id": _USER_ID},
    ) as c:
        yield c

    instance.dependency_overrides.clear()
    _db_module.engine = original


async def test_pg_create_report_persisted(pg_client: AsyncClient) -> None:
    mock_celery = MagicMock()
    mock_celery.send_task.return_value = MagicMock(id="task-integ-001")

    with patch("app.routers.reports.celery_app", mock_celery):
        r = await pg_client.post("/reports")
    assert r.status_code == 202
    report_id = r.json()["id"]
    assert report_id


async def test_pg_poll_returns_pending(pg_client: AsyncClient) -> None:
    mock_celery = MagicMock()
    mock_celery.send_task.return_value = MagicMock(id="task-integ-002")

    with patch("app.routers.reports.celery_app", mock_celery):
        created = (await pg_client.post("/reports")).json()

    r = await pg_client.get(f"/reports/{created['id']}")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


async def test_pg_unknown_report_404(pg_client: AsyncClient) -> None:
    import uuid

    r = await pg_client.get(f"/reports/{uuid.uuid4()}")
    assert r.status_code == 404
