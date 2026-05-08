import asyncio
import json
import random
import uuid

import structlog
from celery import Task
from celery.signals import worker_process_init, worker_process_shutdown
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.celery_app import celery_app
from app.models import Report, ReportStatus
from app.settings import settings

log: structlog.stdlib.BoundLogger = structlog.get_logger()
_engine: AsyncEngine | None = None


def _make_engine() -> AsyncEngine:
    return create_async_engine(str(settings.database_url))


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    return _engine


@worker_process_init.connect
def init_db_engine(**kwargs: object) -> None:
    global _engine
    _engine = _make_engine()


@worker_process_shutdown.connect
def shutdown_db_engine(**kwargs: object) -> None:
    global _engine
    if _engine is not None:
        asyncio.run(_engine.dispose())
        _engine = None


async def _process_report(report_id: str) -> None:
    engine = _get_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        report = await session.get(Report, uuid.UUID(report_id))
        if report is None:
            log.warning("report_not_found", report_id=report_id)
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


async def _fail_report(report_id: str) -> None:
    engine = _get_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        report = await session.get(Report, uuid.UUID(report_id))
        if report is not None:
            report.status = ReportStatus.FAILED
            await session.commit()


@celery_app.task(bind=True, max_retries=5, name="app.tasks.generate_report")
def generate_report(self: Task, report_id: str) -> None:
    try:
        asyncio.run(_process_report(report_id))
    except OperationalError as exc:
        # Transient DB error — retry with exponential backoff; do not mark failed yet.
        delay = 5 * (2**self.request.retries)
        log.warning(
            "report_task_retry",
            report_id=report_id,
            attempt=self.request.retries,
            delay=delay,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=delay) from exc
    except Exception as exc:
        # Fatal — mark failed and do not retry.
        log.error("report_task_failed", report_id=report_id, error=str(exc))
        asyncio.run(_fail_report(report_id))
        raise
