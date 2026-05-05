"""
Unit tests: in-memory SQLite — no Postgres container needed.

The test_engine fixture creates the schema via create_all, and the client
fixture passes a no-op lifespan so the production Alembic migration path
is not exercised. dependency_overrides replaces get_session for all handlers.

Integration tests (test_*_integration.py) are gated behind INTEGRATION=1
and use testcontainers[postgres].
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db import Base, get_session
from app.main import create_app

_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(_SQLITE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(test_engine: AsyncEngine) -> AsyncGenerator[AsyncClient]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )

    async def _get_session() -> AsyncGenerator[AsyncSession]:
        async with factory() as session:
            yield session

    @asynccontextmanager
    async def _null_lifespan(app: FastAPI) -> AsyncGenerator[None]:
        yield

    app_instance = create_app(lifespan_fn=_null_lifespan)
    app_instance.dependency_overrides[get_session] = _get_session

    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as c:
        yield c

    app_instance.dependency_overrides.clear()
