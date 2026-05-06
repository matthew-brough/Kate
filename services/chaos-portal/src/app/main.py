import os
from pathlib import Path

import structlog
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

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

_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_OPEN_PATHS = {"/health", "/ready"}


class TokenAuthMiddleware:
    """Require X-Chaos-Token header on all non-health paths when CHAOS_TOKEN is set."""

    def __init__(self, app: object) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: object, send: object) -> None:
        if CHAOS_TOKEN and scope["type"] == "http" and scope["path"] not in _OPEN_PATHS:
            request = Request(scope)  # type: ignore[arg-type]
            if request.headers.get("X-Chaos-Token") != CHAOS_TOKEN:
                response = Response("Unauthorized", status_code=401)
                await response(scope, receive, send)  # type: ignore[arg-type]
                return
        await self.app(scope, receive, send)  # type: ignore[arg-type]


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
    name = request.path_params["name"]
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
