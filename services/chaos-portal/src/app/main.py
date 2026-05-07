import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp, Receive, Scope, Send

from app import k8s

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()

NAMESPACE = os.getenv("CHAOS_NAMESPACE", "platform")
SERVICES = os.getenv("CHAOS_SERVICES", "orders-api,auth-api,report-api,worker").split(",")
CHAOS_TOKEN = os.getenv("CHAOS_TOKEN", "")


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    if not CHAOS_TOKEN:
        raise RuntimeError("CHAOS_TOKEN env var is not set. Refusing to start unprotected.")
    yield


_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_OPEN_PATHS = {"/health", "/ready"}


class TokenAuthMiddleware:
    """Require X-Chaos-Token header on all non-health paths when CHAOS_TOKEN is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] not in _OPEN_PATHS:
            request = Request(scope)
            incoming = request.headers.get("X-Chaos-Token", "")
            if not hmac.compare_digest(incoming, CHAOS_TOKEN):
                response = Response("Unauthorized", status_code=401)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


async def index(request: Request) -> Response:
    pods = k8s.list_pods(NAMESPACE)
    partitions = k8s.list_partitions(NAMESPACE)
    active_partitions = {p.service for p in partitions}
    return _templates.TemplateResponse(
        request,
        "index.html",
        {
            "pods": pods,
            "services": SERVICES,
            "active_partitions": active_partitions,
            "namespace": NAMESPACE,
        },
    )


async def pod_list(request: Request) -> Response:
    pods = k8s.list_pods(NAMESPACE)
    return _templates.TemplateResponse(
        request, "_pod_list.html", {"pods": pods, "namespace": NAMESPACE}
    )


async def kill_pod(request: Request) -> Response:
    # The token gates "can call this API" but doesn't constrain *what* — without
    # a server-side allowlist a token-holder could delete any pod in the
    # namespace (chaos-portal itself included). k8s pod names are
    # <deployment>-<rs>-<pod>, so prefix-match against `<service>-` is the
    # right shape for the allowlist.
    name = request.path_params["name"]
    if not any(name.startswith(s + "-") for s in SERVICES):
        return Response(f"pod {name!r} not in SERVICES allowlist", status_code=400)
    k8s.delete_pod(NAMESPACE, name)
    log.info("pod_killed", pod=name, namespace=NAMESPACE)
    pods = k8s.list_pods(NAMESPACE)
    return _templates.TemplateResponse(
        request, "_pod_list.html", {"pods": pods, "namespace": NAMESPACE}
    )


async def partition_list(request: Request) -> Response:
    partitions = k8s.list_partitions(NAMESPACE)
    active_partitions = {p.service for p in partitions}
    return _templates.TemplateResponse(
        request,
        "_partition_list.html",
        {"services": SERVICES, "active_partitions": active_partitions, "namespace": NAMESPACE},
    )


async def toggle_partition(request: Request) -> Response:
    service = request.path_params["service"]
    if service not in SERVICES:
        return Response(f"service {service!r} not in SERVICES allowlist", status_code=400)
    active = k8s.toggle_partition(NAMESPACE, service)
    log.info("partition_toggled", service=service, active=active, namespace=NAMESPACE)
    partitions = k8s.list_partitions(NAMESPACE)
    active_partitions = {p.service for p in partitions}
    return _templates.TemplateResponse(
        request,
        "_partition_list.html",
        {"services": SERVICES, "active_partitions": active_partitions, "namespace": NAMESPACE},
    )


async def health(request: Request) -> Response:
    return Response("ok")


async def ready(request: Request) -> Response:
    return Response("ok")


app = Starlette(
    lifespan=lifespan,
    middleware=[Middleware(TokenAuthMiddleware)],
    routes=[
        Route("/", index),
        Route("/pods", pod_list),
        Route("/pods/{name}/kill", kill_pod, methods=["POST"]),
        Route("/partitions", partition_list),
        Route("/partitions/{service}/toggle", toggle_partition, methods=["POST"]),
        Route("/health", health),
        Route("/ready", ready),
    ],
)
