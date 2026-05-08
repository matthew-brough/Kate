from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models import Report, ReportStatus
from app.tasks import _fail_report, _process_report


async def test_process_report_sets_completed(test_engine: AsyncEngine, test_report: Report) -> None:
    # Patch asyncio.sleep to avoid 2-8s delay in tests.
    with (
        patch("app.tasks.asyncio.sleep"),
        patch("app.tasks._get_engine", return_value=test_engine),
    ):
        await _process_report(str(test_report.id))

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    async with factory() as session:
        report = await session.get(Report, test_report.id)
        assert report is not None
        assert report.status == ReportStatus.COMPLETED
        assert report.result is not None


async def test_process_report_unknown_id_is_noop(test_engine: AsyncEngine) -> None:
    import uuid

    with (
        patch("app.tasks.asyncio.sleep"),
        patch("app.tasks._get_engine", return_value=test_engine),
    ):
        # Should not raise; just logs a warning and returns.
        await _process_report(str(uuid.uuid4()))


async def test_fail_report_sets_failed(test_engine: AsyncEngine, test_report: Report) -> None:
    with patch("app.tasks._get_engine", return_value=test_engine):
        await _fail_report(str(test_report.id))

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        test_engine, expire_on_commit=False
    )
    async with factory() as session:
        report = await session.get(Report, test_report.id)
        assert report is not None
        assert report.status == ReportStatus.FAILED
