import hmac
import os
import re
from base64 import b64decode
from binascii import Error as BinasciiError
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
DEFAULT_SERVICES = "orders-api,auth-api,report-api,worker"
DEFAULT_KILL_TARGETS = f"{DEFAULT_SERVICES},gateway,loadgen,redis-master"


def _split_csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


SERVICES = _split_csv_env("CHAOS_SERVICES", DEFAULT_SERVICES)
KILL_TARGETS = _split_csv_env("CHAOS_KILL_TARGETS", DEFAULT_KILL_TARGETS)
LOADGEN_DEPLOYMENT = os.getenv("CHAOS_LOADGEN_DEPLOYMENT", "loadgen")
CHAOS_AUTH_MODE = os.getenv("CHAOS_AUTH_MODE", "token")
CHAOS_TOKEN = os.getenv("CHAOS_TOKEN", "")
AUTH_REALM = "chaos-portal"


@dataclass(frozen=True)
class LoadgenProfile:
    name: str
    label: str
    replicas: int
    users: int
    spawn_rate: int


LOADGEN_PROFILES = (
    LoadgenProfile("baseline", "baseline", replicas=1, users=5, spawn_rate=1),
    LoadgenProfile("busy", "busy", replicas=2, users=25, spawn_rate=5),
    LoadgenProfile("surge", "surge", replicas=3, users=100, spawn_rate=20),
    LoadgenProfile("breakpoint", "breakpoint", replicas=5, users=250, spawn_rate=50),
)
LOADGEN_PROFILE_MAP = {profile.name: profile for profile in LOADGEN_PROFILES}


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    if CHAOS_AUTH_MODE not in {"dev", "token"}:
        raise RuntimeError("CHAOS_AUTH_MODE must be 'dev' or 'token'.")
    if CHAOS_AUTH_MODE == "token" and not CHAOS_TOKEN:
        raise RuntimeError("CHAOS_TOKEN env var is not set. Refusing to start unprotected.")
    if CHAOS_AUTH_MODE == "dev":
        log.warning("chaos_portal_auth_disabled", mode=CHAOS_AUTH_MODE)
    yield


_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_OPEN_PATHS = {"/health", "/ready"}
_DEPLOYMENT_POD_SUFFIX = re.compile(r"[a-z0-9]{8,10}-[a-z0-9]{5}")


class TokenAuthMiddleware:
    """Gate chaos actions unless the portal is running in explicit dev auth mode."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["path"] not in _OPEN_PATHS
            and CHAOS_AUTH_MODE != "dev"
        ):
            request = Request(scope)
            if not _is_authorized(request):
                response = Response(
                    "Unauthorized",
                    status_code=401,
                    headers={"WWW-Authenticate": f'Basic realm="{AUTH_REALM}"'},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _is_authorized(request: Request) -> bool:
    incoming = request.headers.get("X-Chaos-Token", "")
    if _token_matches(incoming):
        return True

    auth_header = request.headers.get("Authorization", "")
    scheme, _, credentials = auth_header.partition(" ")
    if scheme.lower() == "bearer":
        return _token_matches(credentials)
    if scheme.lower() == "basic":
        return _basic_password_matches(credentials)
    return False


def _token_matches(value: str) -> bool:
    return bool(CHAOS_TOKEN) and bool(value) and hmac.compare_digest(value, CHAOS_TOKEN)


def _basic_password_matches(credentials: str) -> bool:
    try:
        decoded = b64decode(credentials, validate=True).decode()
    except (BinasciiError, UnicodeDecodeError, ValueError):
        return False
    _, separator, password = decoded.partition(":")
    return bool(separator) and _token_matches(password)


def _is_killable_pod(name: str) -> bool:
    return any(
        name.startswith(f"{target}-")
        and _DEPLOYMENT_POD_SUFFIX.fullmatch(name.removeprefix(f"{target}-")) is not None
        for target in KILL_TARGETS
    )


def _pod_list_context(pods: list[k8s.PodInfo]) -> dict[str, object]:
    return {
        "pods": pods,
        "killable_pods": {pod.name for pod in pods if _is_killable_pod(pod.name)},
        "namespace": NAMESPACE,
    }


def _loadgen_context() -> dict[str, object]:
    status = k8s.get_loadgen_status(NAMESPACE, LOADGEN_DEPLOYMENT)
    active_profile = next(
        (
            profile.name
            for profile in LOADGEN_PROFILES
            if (
                status.replicas == profile.replicas
                and status.users == str(profile.users)
                and status.spawn_rate == str(profile.spawn_rate)
            )
        ),
        "",
    )
    return {
        "loadgen_status": status,
        "loadgen_profiles": LOADGEN_PROFILES,
        "active_loadgen_profile": active_profile,
        "namespace": NAMESPACE,
    }


async def index(request: Request) -> Response:
    pods = k8s.list_pods(NAMESPACE)
    partitions = k8s.list_partitions(NAMESPACE)
    active_partitions = {p.service for p in partitions}
    context: dict[str, object] = {
        **_pod_list_context(pods),
        "services": SERVICES,
        "active_partitions": active_partitions,
    }
    context.update(_loadgen_context())
    return _templates.TemplateResponse(
        request,
        "index.html",
        context,
    )


async def pod_list(request: Request) -> Response:
    pods = k8s.list_pods(NAMESPACE)
    return _templates.TemplateResponse(
        request, "_pod_list.html", _pod_list_context(pods)
    )


async def kill_pod(request: Request) -> Response:
    # The token gates "can call this API" but doesn't constrain *what* — without
    # a server-side allowlist a token-holder could delete any pod in the
    # namespace (chaos-portal itself included). Match the Deployment pod-name
    # shape against explicit kill targets so auth-api-postgresql, migration
    # jobs, and other similarly-prefixed pods are not swept in.
    name = request.path_params["name"]
    if not _is_killable_pod(name):
        return Response(f"pod {name!r} not in KILL_TARGETS allowlist", status_code=400)
    k8s.delete_pod(NAMESPACE, name)
    log.info("pod_killed", pod=name, namespace=NAMESPACE)
    pods = k8s.list_pods(NAMESPACE)
    return _templates.TemplateResponse(
        request, "_pod_list.html", _pod_list_context(pods)
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


async def loadgen_panel(request: Request) -> Response:
    return _templates.TemplateResponse(request, "_loadgen_panel.html", _loadgen_context())


async def apply_loadgen_profile(request: Request) -> Response:
    profile_name = request.path_params["profile"]
    profile = LOADGEN_PROFILE_MAP.get(profile_name)
    if profile is None:
        return Response(f"loadgen profile {profile_name!r} not configured", status_code=400)
    k8s.scale_loadgen(
        NAMESPACE,
        LOADGEN_DEPLOYMENT,
        replicas=profile.replicas,
        users=profile.users,
        spawn_rate=profile.spawn_rate,
    )
    log.info(
        "loadgen_profile_applied",
        profile=profile.name,
        replicas=profile.replicas,
        users=profile.users,
        spawn_rate=profile.spawn_rate,
        deployment=LOADGEN_DEPLOYMENT,
        namespace=NAMESPACE,
    )
    return _templates.TemplateResponse(request, "_loadgen_panel.html", _loadgen_context())


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
        Route("/loadgen", loadgen_panel),
        Route("/loadgen/{profile}/apply", apply_loadgen_profile, methods=["POST"]),
        Route("/health", health),
        Route("/ready", ready),
    ],
)
