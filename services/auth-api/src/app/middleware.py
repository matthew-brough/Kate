import time
import uuid

import structlog
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
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
