from fastapi import APIRouter
from pydantic import BaseModel

from app.settings import settings

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
    )


@router.get("/ready", response_model=HealthResponse, include_in_schema=False)
async def ready() -> HealthResponse:
    """Readiness probe — override in concrete services to check dependencies."""
    return HealthResponse(
        status="ready",
        service=settings.service_name,
        version=settings.service_version,
    )
