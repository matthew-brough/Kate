from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging
from app.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.routers import health, proxy
from app.settings import settings
from app.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    configure_telemetry(app)
    redis_client = redis.from_url(
        settings.effective_rate_limit_redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        app.state.http_client = client
        app.state.redis_client = redis_client
        try:
            yield
        finally:
            await redis_client.aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        lifespan=lifespan,
        redoc_url=None,
    )

    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    app.include_router(health.router)
    app.include_router(proxy.router)

    return app


app = create_app()
