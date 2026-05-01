import time
import uuid
from collections import defaultdict, deque

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

# (max_requests, window_seconds) per path
_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/auth/token": (10, 60),
    "/api/auth/register": (5, 60),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rule = _RATE_LIMITS.get(request.url.path)
        if rule is not None:
            limit, window = rule
            client_ip = request.client.host if request.client else "unknown"
            key = (client_ip, request.url.path)
            now = time.monotonic()
            dq = self._windows[key]
            while dq and dq[0] < now - window:
                dq.popleft()
            if len(dq) >= limit:
                logger.warning("rate_limit_exceeded", path=request.url.path, client=client_ip)
                return JSONResponse({"detail": "Too many requests"}, status_code=429)
            dq.append(now)
        return await call_next(request)


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
