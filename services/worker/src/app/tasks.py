import asyncio
import json
import random
import uuid

import structlog
from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.models import Report, ReportStatus
from app.settings import settings

log: structlog.stdlib.BoundLogger = structlog.get_logger()


def _make_engine() -> object:
    # NullPool: each asyncio.run() call gets its own connections — safe after fork.
    return create_async_engine(str(settings.database_url), poolclass=NullPool)


async def _process_report(report_id: str) -> None:
    engine = _make_engine()  # type: ignore[assignment]
    async with AsyncSession(engine, expire_on_commit=False) as session:  # type: ignore[arg-type]
        report = await session.get(Report, uuid.UUID(report_id))
        if report is None:
            log.warning("report_not_found", report_id=report_id)
            await engine.dispose()  # type: ignore[union-attr]
            return

        report.status = ReportStatus.PROCESSING
        await session.commit()
        log.info("report_processing", report_id=report_id)

        # Simulate variable-duration work; makes timing traces interesting.
        await asyncio.sleep(random.uniform(2.0, 8.0))

        report.status = ReportStatus.COMPLETED
        report.result = json.dumps(
            {
                "row_count": random.randint(100, 50_000),
                "duration_s": round(random.uniform(2.0, 8.0), 2),
            }
        )
        await session.commit()
        log.info("report_completed", report_id=report_id)

    await engine.dispose()  # type: ignore[union-attr]


async def _fail_report(report_id: str) -> None:
    engine = _make_engine()  # type: ignore[assignment]
    async with AsyncSession(engine, expire_on_commit=False) as session:  # type: ignore[arg-type]
        report = await session.get(Report, uuid.UUID(report_id))
        if report is not None:
            report.status = ReportStatus.FAILED
            await session.commit()
    await engine.dispose()  # type: ignore[union-attr]


@celery_app.task(bind=True, max_retries=3, name="app.tasks.generate_report")
def generate_report(self: Task, report_id: str) -> None:
    try:
        asyncio.run(_process_report(report_id))
    except Exception as exc:
        log.error("report_task_error", report_id=report_id, error=str(exc))
        asyncio.run(_fail_report(report_id))
        raise self.retry(exc=exc, countdown=5) from exc
