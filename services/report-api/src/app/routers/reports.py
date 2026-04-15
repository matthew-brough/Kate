import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery_app
from app.db import get_session
from app.models import Report
from app.schemas import ReportRead

router = APIRouter(prefix="/reports", tags=["reports"])
log: structlog.stdlib.BoundLogger = structlog.get_logger()


@router.post("", response_model=ReportRead, status_code=status.HTTP_202_ACCEPTED)
async def create_report(
    x_user_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> Report:
    user_id = x_user_id or "anonymous"
    report = Report(user_id=user_id)
    session.add(report)
    await session.commit()
    await session.refresh(report)

    celery_app.send_task("app.tasks.generate_report", args=[str(report.id)])
    log.info("report_enqueued", report_id=str(report.id), user_id=user_id)
    return report


@router.get("", response_model=list[ReportRead])
async def list_reports(
    x_user_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> list[Report]:
    user_id = x_user_id or "anonymous"
    result = await session.execute(
        select(Report).where(Report.user_id == user_id).order_by(Report.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{report_id}", response_model=ReportRead)
async def get_report(
    report_id: uuid.UUID,
    x_user_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> Report:
    report = await session.get(Report, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    user_id = x_user_id or "anonymous"
    if report.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return report
