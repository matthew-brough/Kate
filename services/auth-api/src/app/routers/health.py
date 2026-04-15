from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.settings import settings

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict[str, str]


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get("/ready", response_model=ReadyResponse, include_in_schema=False)
async def ready(session: AsyncSession = Depends(get_session)) -> ReadyResponse:
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    overall = "ready" if db_status == "ok" else "degraded"
    return ReadyResponse(
        status=overall,
        service=settings.service_name,
        version=settings.service_version,
        checks={"database": db_status},
    )
