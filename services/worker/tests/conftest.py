import os
import tempfile
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base, Report


@pytest.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    # Use a temp file so the DB survives engine.dispose() calls inside tasks.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()
    os.unlink(db_path)


@pytest.fixture
async def test_report(test_engine: AsyncEngine) -> AsyncGenerator[Report]:
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    async with factory() as session:
        report = Report(user_id="test-user")
        session.add(report)
        await session.commit()
        await session.refresh(report)
    yield report
