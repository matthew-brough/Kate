# -*- mode: Python -*-
# Tilt dev loop for the Kate platform.
# Requires: k3d cluster running (`make cluster-up`), Tilt >= 0.33.

REGISTRY = "registry.localhost:5001"
NAMESPACE = "platform"


def svc(name, port_forward=None):
    """Register a FastAPI service: build → deploy → optional port-forward."""
    docker_build(
        REGISTRY + "/" + name,
        "services/" + name,
        target = "dev",
        live_update = [
            sync("services/" + name + "/src/app", "/app/src/app"),
        ],
    )
    k8s_yaml(
        helm(
            "charts/" + name,
            name      = name,
            namespace = NAMESPACE,
            values    = ["charts/" + name + "/ci/dev-values.yaml"],
            set       = [
                "image.repository=" + REGISTRY + "/" + name,
                "image.tag=latest",
            ],
        )
    )
    fwds = [port_forward + ":8000"] if port_forward else []
    k8s_resource(name, port_forwards=fwds, labels=["services"])


# ── orders-api ────────────────────────────────────────────────────────────────
svc("orders-api", port_forward=8000)

# ── auth-api ──────────────────────────────────────────────────────────────────
svc("auth-api", port_forward=8001)

# ── report-api ────────────────────────────────────────────────────────────────
svc("report-api", port_forward=8002)

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
svc("chaos-portal", port_forward=8090)

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
