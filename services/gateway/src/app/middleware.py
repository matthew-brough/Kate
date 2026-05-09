import time
import uuid
from typing import Protocol, cast

import redis.exceptions
import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.settings import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

class RateLimitRedis(Protocol):
    async def incr(self, name: str) -> int: ...

    async def expire(self, name: str, time: int) -> object: ...


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rule = _rate_limits().get(request.url.path)
        if rule is not None:
            limit, window = rule
            client_ip = _client_identity(request)
            redis_client = cast(
                RateLimitRedis | None,
                getattr(request.app.state, "redis_client", None),
            )
            count = await _increment_rate_limit(redis_client, client_ip, request.url.path, window)
            if count > limit:
                logger.warning("rate_limit_exceeded", path=request.url.path, client=client_ip)
                return JSONResponse({"detail": "Too many requests"}, status_code=429)
        return await call_next(request)


def _rate_limits() -> dict[str, tuple[int, int]]:
    # (max_requests, window_seconds) per path. Kept behind settings so dev/load
    # environments can raise auth ceilings without changing production defaults.
    return {
        "/api/auth/token": (
            settings.rate_limit_auth_token_requests,
            settings.rate_limit_auth_token_window_seconds,
        ),
        "/api/auth/register": (
            settings.rate_limit_auth_register_requests,
            settings.rate_limit_auth_register_window_seconds,
        ),
    }


def _client_identity(request: Request) -> str:
    if settings.rate_limit_trust_x_forwarded_for:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            first_hop = forwarded_for.split(",", 1)[0].strip()
            if first_hop:
                return first_hop
    return request.client.host if request.client else "unknown"


async def _increment_rate_limit(
    redis_client: RateLimitRedis | None,
    client_ip: str,
    path: str,
    window: int,
) -> int:
    if redis_client is None:
        logger.warning("rate_limit_redis_missing", path=path)
        return 0

    bucket = int(time.time() // window)
    key = f"rate-limit:{path}:{client_ip}:{bucket}"
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window)
        return count
    except redis.exceptions.RedisError as exc:
        logger.warning("rate_limit_redis_error", path=path, error=str(exc))
        return 0


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())

        span = trace.get_current_span()
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x") if ctx and ctx.is_valid else ""

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
        )

        t0 = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        logger.info(
            "request",
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response
