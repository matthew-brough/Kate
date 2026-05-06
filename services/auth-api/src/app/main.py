import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

import app.db as _db
from app.logging_config import configure_logging
from app.middleware import RequestLoggingMiddleware
from app.routers import auth, health
from app.settings import settings
from app.telemetry import configure_telemetry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    configure_logging()
    configure_telemetry(app)
    alembic_cfg = Config("alembic.ini")
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    yield
    await _db.engine.dispose()


def create_app(lifespan_fn: Callable[[FastAPI], Any] = lifespan) -> FastAPI:
    app = FastAPI(
        title=settings.service_name,
        version=settings.service_version,
        lifespan=lifespan_fn,
        redoc_url=None,
    )

    app.add_middleware(RequestLoggingMiddleware)

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    app.include_router(health.router)
    app.include_router(auth.router)

    return app


app = create_app()
