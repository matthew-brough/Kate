from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.routers import health
from app.settings import settings
from app.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    configure_telemetry(app)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        lifespan=lifespan,
        redoc_url=None,
    )

    app.add_middleware(RequestLoggingMiddleware)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    app.include_router(health.router)

    return app


app = create_app()
