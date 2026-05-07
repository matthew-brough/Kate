# -*- mode: Python -*-
# Tilt dev loop for the Kate platform.
# Requires: k3d cluster running (`make cluster-up`), Tilt >= 0.33.

REGISTRY = "registry.localhost:5001"
NAMESPACE = "platform"


def _load_env(path):
    """Parse a KEY=VALUE .env file. Fail clearly if missing or malformed.

    The chart's `required` template guards reject empty values at install time,
    so we only need to surface a friendly message about the missing source file.
    """
    if not os.path.exists(path):
        fail(
            ".env not found at " + path + " — copy .env.example to .env and fill it in"
        )
    env = {}
    for line in str(read_file(path)).split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            fail(".env: expected KEY=VALUE, got: " + line)
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _require(env, key):
    if not env.get(key):
        fail(".env: required key " + key + " is missing or empty")
    return env[key]


_ENV = _load_env(".env")
JWT_SECRET = _require(_ENV, "APP_JWT_SECRET")
DB_PASSWORDS = {
    "auth-api":   _require(_ENV, "APP_AUTH_DB_PASSWORD"),
    "orders-api": _require(_ENV, "APP_ORDERS_DB_PASSWORD"),
    "report-api": _require(_ENV, "APP_REPORT_DB_PASSWORD"),
}
CHAOS_TOKEN = _require(_ENV, "CHAOS_TOKEN")

# Charts that need jwtSecret injected from .env (auth-api and gateway must agree
# on the value or token validation silently fails).
_NEEDS_JWT = {"auth-api": True, "gateway": True}


def svc(name, port_forward=None, live_sync=True):
    """Register a FastAPI service: build → deploy → optional port-forward.

    `live_sync=False` for services whose CMD lacks `--reload` (e.g. chaos-portal,
    where uvicorn's reloader misbehaves). Tilt does a full image rebuild on file
    change, which picks up the new code via a fresh pod.
    """
    build_kwargs = {"target": "dev"}
    if live_sync:
        build_kwargs["live_update"] = [
            sync("services/" + name + "/src/app", "/app/src/app"),
        ]
    docker_build(REGISTRY + "/" + name, "services/" + name, **build_kwargs)
    set_args = [
        "image.repository=" + REGISTRY + "/" + name,
        "image.tag=latest",
    ]
    if _NEEDS_JWT.get(name):
        set_args.append("jwtSecret=" + JWT_SECRET)
    if name in DB_PASSWORDS:
        set_args.append("postgresql.auth.password=" + DB_PASSWORDS[name])
    if name == "chaos-portal":
        set_args.append("chaosToken=" + CHAOS_TOKEN)
    k8s_yaml(
        helm(
            "charts/" + name,
            name      = name,
            namespace = NAMESPACE,
            values    = ["charts/" + name + "/ci/dev-values.yaml"],
            set       = set_args,
        )
    )
    fwds = [str(port_forward) + ":8000"] if port_forward else []
    k8s_resource(name, port_forwards=fwds, labels=["services"])


def svc_with_db(name, port_forward=None):
    """Register a FastAPI service whose chart bundles a postgres sub-deployment."""
    svc(name, port_forward=port_forward)
    k8s_resource(name + "-postgresql", labels=["postgres"])


# ── orders-api ────────────────────────────────────────────────────────────────
svc_with_db("orders-api", port_forward=8000)

# ── auth-api ──────────────────────────────────────────────────────────────────
svc_with_db("auth-api", port_forward=8001)

# ── report-api ────────────────────────────────────────────────────────────────
svc("report-api", port_forward=8002)
k8s_resource("report-api-postgresql", labels=["postgres"])

# ── gateway (main ingress, also exposed via Traefik at kate.localhost) ────────
svc("gateway", port_forward=8080)

# ── worker (no HTTP port — Celery process) ────────────────────────────────────
docker_build(
    REGISTRY + "/worker",
    "services/worker",
    target = "dev",
)
k8s_yaml(
    helm(
        "charts/worker",
        name      = "worker",
        namespace = NAMESPACE,
        values    = ["charts/worker/ci/dev-values.yaml"],
        set       = [
            "image.repository=" + REGISTRY + "/worker",
            "image.tag=latest",
        ],
    )
)
k8s_resource("worker", labels=["services"])

# ── redis (Celery broker) ─────────────────────────────────────────────────────
k8s_yaml(
    helm(
        "charts/redis",
        name      = "redis",
        namespace = NAMESPACE,
        values    = ["charts/redis/ci/dev-values.yaml"],
    )
)
k8s_resource("redis-master", port_forwards=["6379:6379"], labels=["infra"])

# ── chaos-portal (Starlette + HTMX, pod kill + network partition) ────────────
svc("chaos-portal", port_forward=8090, live_sync=False)

# ── loadgen (Locust headless, ~5 RPS continuous traffic) ──────────────────────
docker_build(
    REGISTRY + "/loadgen",
    "services/loadgen",
    target = "dev",
    live_update = [
        sync("services/loadgen/src/app", "/app/src/app"),
    ],
)
k8s_yaml(
    helm(
        "charts/loadgen",
        name      = "loadgen",
        namespace = NAMESPACE,
        values    = ["charts/loadgen/ci/dev-values.yaml"],
        set       = [
            "image.repository=" + REGISTRY + "/loadgen",
            "image.tag=latest",
        ],
    )
)
k8s_resource("loadgen", labels=["infra"])
