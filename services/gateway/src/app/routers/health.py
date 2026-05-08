import asyncio
from typing import cast

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.settings import settings

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(HealthResponse):
    dependencies: dict[str, str]


UPSTREAM_HEALTHCHECKS = {
    "auth-api": "/health",
    "orders-api": "/health",
    "report-api": "/health",
}


@router.get("/health", response_model=HealthResponse, include_in_schema=False)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
    )


async def _check_upstream(
    client: httpx.AsyncClient,
    name: str,
    base_url: str,
    path: str,
) -> tuple[str, str]:
    try:
        response = await client.get(
            f"{base_url.rstrip('/')}{path}",
            timeout=settings.readiness_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return name, "unavailable"
    return name, "ready"


@router.get("/ready", response_model=ReadinessResponse, include_in_schema=False)
async def ready(request: Request) -> ReadinessResponse | JSONResponse:
    client = cast(httpx.AsyncClient, request.app.state.http_client)
    checks = await asyncio.gather(
        _check_upstream(
            client,
            "auth-api",
            settings.auth_api_url,
            UPSTREAM_HEALTHCHECKS["auth-api"],
        ),
        _check_upstream(
            client,
            "orders-api",
            settings.orders_api_url,
            UPSTREAM_HEALTHCHECKS["orders-api"],
        ),
        _check_upstream(
            client,
            "report-api",
            settings.report_api_url,
            UPSTREAM_HEALTHCHECKS["report-api"],
        ),
    )
    dependencies = dict(checks)
    status = "ready" if all(value == "ready" for value in dependencies.values()) else "degraded"
    payload = ReadinessResponse(
        status=status,
        service=settings.service_name,
        version=settings.service_version,
        dependencies=dependencies,
    )
    if status != "ready":
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
