from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

import app.db as _db
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.routers import health, reports
from app.settings import settings
from app.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    configure_telemetry(app)
    yield
    await _db.engine.dispose()


def create_app(
    lifespan_fn: Callable[[FastAPI], AbstractAsyncContextManager[None]] = lifespan,
) -> FastAPI:
    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        lifespan=lifespan_fn,
        redoc_url=None,
    )

    app.add_middleware(RequestLoggingMiddleware)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    app.include_router(health.router)
    app.include_router(reports.router)

    return app


app = create_app()
