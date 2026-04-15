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

    original_engine = _db_module.engine
    _db_module.engine = test_engine

    app_instance = create_app()
    app_instance.dependency_overrides[get_session] = _get_session

    async with AsyncClient(
        transport=ASGITransport(app=app_instance), base_url="http://test"
    ) as c:
        yield c

    app_instance.dependency_overrides.clear()
    _db_module.engine = original_engine
