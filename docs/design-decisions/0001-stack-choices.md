# Design Decision 0001: Stack Choices for Kate

**Status**: Current  
**Date**: 2026-04-14  
**Scope**: Platform runtime, service framework, local cluster, and developer tooling

---

## Context

Building a portfolio-grade mock e-commerce backend that demonstrates production-level
thinking across service architecture, Kubernetes mechanics, observability, GitOps, and
chaos engineering. The running cluster is a *source* of artifacts, not a live demo.

Every choice below was evaluated on two axes:

1. **Learning value** — does building this teach the mechanic, or just use it?
2. **Review signal** — does the choice show depth through implementation or judgment through reuse?

---

## Decision

### Python 3.14

The repo targets Python 3.14. No good reason to target an earlier version for a new
project. Enables improved typing features (PEP 695 type aliases, `@override`, etc.).

### FastAPI

**Chosen over**: Flask, Django REST Framework, Starlette (bare).

FastAPI is the de-facto standard for Python async APIs. The depth signal comes from *how*
it is used: typed Pydantic schemas at every boundary, lifespan context managers, dependency
injection for session management, OTel auto-instrumentation. A raw framework choice is less
interesting than the integration choices.

The single `services/_template` is forked (copied, not sub-packaged) into each service so
every service is independently deployable. No shared library means no shared-library
version skew at the cost of some duplication — acceptable at this scale.

### SQLAlchemy 2.x (async) + asyncpg

**Chosen over**: raw psycopg3, SQLModel, Django ORM.

SQLAlchemy 2.x is the most widely deployed Python ORM, and its async API (`create_async_engine`,
`async_sessionmaker`) is now first-class. asyncpg is the fastest PostgreSQL async driver.
Using Alembic for migrations is standard production practice; `create_all()` was only used
for the earliest service scaffold and was replaced by Alembic once schemas stabilized.

### Celery + Redis

**Chosen over**: Dramatiq, RQ, Temporal, hand-rolled queue.

Celery is the Python ecosystem default for task queuing. Redis is the broker for report
generation and the metric source for worker autoscaling. A hand-rolled queue would be
interesting academically but would pull focus from the Kubernetes mechanics that are the
portfolio centrepiece.

See [design decision 0002](0002-queue-depth-hpa.md) for the queue-depth autoscaling
decision that makes Celery interesting from a Kubernetes angle.

### OpenTelemetry SDK + Collector

**Chosen over**: Datadog SDK, direct Jaeger/Zipkin client, no tracing.

OTel is vendor-neutral. The Collector sits between services and backends
(Tempo, Prometheus, Loki), adding sampling and batching without touching service code.
The collector config is DIY — that's where the learning is: pipeline processors, tail
sampling, attribute filtering. [Design decision 0004](0004-observability-stack.md) covers
the observability stack.

### structlog (JSON logging)

**Chosen over**: standard `logging` only, loguru.

structlog's `contextvars` integration means every log line emitted during a request
automatically carries `request_id` and `trace_id` — critical for the log→trace correlation
story. JSON output is natively parseable by Promtail → Loki without a parser
plugin.

### k3d + k3s

**Chosen over**: kind, minikube, full EKS/GKE.

k3d runs a multi-node k3s cluster inside Docker containers with a built-in local registry.
It boots in ~10 seconds on a laptop, supports real Traefik ingress, and is close enough to
production k8s that all mechanics (HPA, PDB, NetworkPolicy) behave correctly. No cloud
account required.

### ArgoCD (app-of-apps)

**Chosen over**: Flux, raw `kubectl apply`, Helm releases only.

ArgoCD's app-of-apps pattern (one root Application pointing to a `gitops/apps/` directory
of per-environment Applications) is the most widely taught GitOps pattern. The key design
signal is the *separation of concerns*: CI pushes an image tag; ArgoCD reconciles state.
[Design decision 0003](0003-gitops-argocd.md) covers the GitOps topology in detail.

### kube-prometheus-stack + Loki + Tempo

**Chosen over**: Elastic stack, Datadog, Victoria Metrics, rolling Prometheus by hand.

Industry defaults. The integration is the value: ServiceMonitors auto-scrape services,
Promtail ships structured logs with trace IDs, Grafana derived fields wire log lines to
Tempo traces. [Design decision 0004](0004-observability-stack.md) covers the observability
stack.

### Tilt (inner dev loop)

**Chosen over**: Skaffold, raw `docker build && kubectl rollout`.

Tilt's `live_update` syncs changed Python source files into a running container without a
full image rebuild, making the edit→refresh cycle ~1 s instead of ~30 s. The `Tiltfile` is
Python-like, version-controlled, and self-documenting.

### uv (Python dep management)

**Chosen over**: pip + pip-tools, Poetry, PDM.

uv resolves and installs a full dependency tree in milliseconds, ships a lock file, and is
used as the package installer inside Dockerfiles via `COPY --from=ghcr.io/astral-sh/uv`.
This eliminates the "slow pip install" layer that often dominates container build time.

### Not chosen: service mesh (Istio / Linkerd)

A service mesh would add mTLS, observability sidecars, and traffic management. At this
scale, it adds ~500 ms startup latency, significant resource overhead, and non-trivial
debugging surface. The same observability outcomes (traces, metrics, retries) are achieved
with the OTel SDK in each service, which teaches more and is less opaque.

### Not chosen: TLS / cert-manager

TLS termination via cert-manager + Let's Encrypt is a well-understood add-on that does not
teach new mechanics for this portfolio. Traefik's TLS support is noted; the deliberate
omission is documented so readers see it as a considered decision rather than a gap.

---

## Consequences

- Services share a consistent shape: all forks of `services/_template`. Onboarding a new
  service means copying the template and adding domain logic — not learning a different
  framework pattern.
- The observability stack requires the OTel collector to be deployed before
  traces appear in Tempo. `APP_OTLP_ENABLED=false` is the safe default for local dev.
- SQLite is used for unit tests; real Postgres is required for integration tests
  (`INTEGRATION=1`). The `native_enum=False` flag on `OrderStatus` makes the model
  compatible with both.
