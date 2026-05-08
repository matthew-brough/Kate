from typing import cast

import httpx
import structlog
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.auth import AuthDep, TokenPayload
from app.settings import settings

router = APIRouter()
log: structlog.stdlib.BoundLogger = structlog.get_logger()

_STRIP_REQUEST_HEADERS = {
    "host",
    "content-length",
    "authorization",
    "x-user-id",
    "x-username",
}

_STRIP_RESPONSE_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _get_client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http_client)


async def _proxy(
    request: Request,
    target_url: str,
    user: TokenPayload | None = None,
) -> Response:
    client = _get_client(request)

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _STRIP_REQUEST_HEADERS
    }
    if user is not None:
        headers["X-User-Id"] = user.sub
        headers["X-Username"] = user.username

    body = await request.body()

    try:
        upstream = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )
    except httpx.RequestError as exc:
        log.warning("upstream_error", target=target_url, error=str(exc))
        return Response(content=b'{"detail":"upstream unavailable"}', status_code=503)

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={
            k: v
            for k, v in upstream.headers.items()
            if k.lower() not in _STRIP_RESPONSE_HEADERS
        },
    )


# ── Auth routes (no JWT required) ────────────────────────────────────────────


@router.api_route(
    "/api/auth/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["proxy"],
)
async def proxy_auth(path: str, request: Request) -> Response:
    target = f"{settings.auth_api_url}/auth/{path}"
    return await _proxy(request, target)


# ── Orders routes (JWT required) ─────────────────────────────────────────────


@router.api_route(
    "/api/orders/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["proxy"],
)
async def proxy_orders(path: str, request: Request, user: AuthDep) -> Response:
    target = f"{settings.orders_api_url}/orders/{path}"
    return await _proxy(request, target, user)


@router.api_route(
    "/api/orders",
    methods=["GET", "POST"],
    tags=["proxy"],
)
async def proxy_orders_root(request: Request, user: AuthDep) -> Response:
    target = f"{settings.orders_api_url}/orders"
    return await _proxy(request, target, user)


# ── Reports routes (JWT required) ────────────────────────────────────────────


@router.api_route(
    "/api/reports/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    tags=["proxy"],
)
async def proxy_reports(path: str, request: Request, user: AuthDep) -> Response:
    target = f"{settings.report_api_url}/reports/{path}"
    return await _proxy(request, target, user)


@router.api_route(
    "/api/reports",
    methods=["GET", "POST"],
    tags=["proxy"],
)
async def proxy_reports_root(request: Request, user: AuthDep) -> Response:
    target = f"{settings.report_api_url}/reports"
    return await _proxy(request, target, user)
