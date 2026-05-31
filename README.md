# Kate

A production-grade mock e-commerce platform on Kubernetes — built to demonstrate platform engineering across the full delivery stack: microservices, GitOps, autoscaling, observability, chaos engineering, and CI/CD.

## Architecture

```
          ┌─────────┐
Browser → │ gateway │ JWT-validating reverse proxy
          └────┬────┘
       ┌───────┼───────┐
       ▼       ▼       ▼
  auth-api  orders-api  report-api ──► Redis ──► worker
  Postgres  Postgres    Postgres(shared)          (Celery)
```

See [`docs/architecture.md`](docs/architecture.md) for full data flows, networking topology, and observability wiring.

## Services

| Service | Port | Description |
|---------|------|-------------|
| gateway | 8080 | JWT validation, reverse proxy to all backends |
| orders-api | 8000 | Order CRUD (SQLAlchemy 2 async + asyncpg) |
| auth-api | 8001 | Registration, bcrypt passwords, JWT minting |
| report-api | 8002 | Async report requests; Celery enqueue + 202 poll |
| worker | — | Celery worker; writes COMPLETED/FAILED to Postgres |
| loadgen | — | Locust headless, ~5 VUs, continuous synthetic traffic |
| chaos-portal | 8090 | Starlette + HTMX; pod kill + network partition toggle |

## Quick start

```bash
# 1. Create local config/secrets for Tilt and Helm
cp .env.example .env
# edit .env if you do not want to use the checked-in dev defaults

# 2. Create k3d cluster (1 server + 2 agents, local registry, Traefik ingress)
make cluster-up

# 3. Build, deploy, and live-reload all services
make dev

# 4. Install observability stack (separate terminal, one-time)
set -a; . ./.env; set +a
make obs-up

# Grafana:  kubectl -n observability port-forward svc/kube-prometheus-stack-grafana 3000:80
# Gateway:  http://kate.localhost  (via Traefik)
# Seed:     uv run python scripts/seed.py
```

Optional add-ons (run once after `cluster-up`):

```bash
make keda-up    # KEDA for worker queue-depth autoscaling
make argocd-up  # ArgoCD GitOps — app-of-apps for dev + staging; do not run with Tilt in the same namespace
```

## Stack

| Layer | Technology |
|-------|------------|
| Runtime | Python 3.14, FastAPI / Starlette, Celery, SQLAlchemy 2 async |
| Containers | Docker (multi-stage), uv, k3d, Traefik |
| Orchestration | Kubernetes (k3d), Helm, ArgoCD, KEDA |
| Observability | kube-prometheus-stack, Loki, Promtail, Tempo, OTel Collector, Grafana |
| CI/CD | GitHub Actions, GHCR, chart-testing |
| Dev tools | Tilt, ruff, pyright, pytest + testcontainers |

## CI

Three workflows:

| Workflow | Trigger | Jobs |
|----------|---------|------|
| [`ci.yml`](.github/workflows/ci.yml) | push to `main` + PR | ruff · pyright · pytest · integration tests (INTEGRATION=1) |
| [`build.yml`](.github/workflows/build.yml) | push to `main` | docker build → push to GHCR |
| [`helm.yml`](.github/workflows/helm.yml) | push to `main` + PR | helm lint · kubeconform · ct lint |

Integration tests use a real Postgres service in CI. Local integration runs can fall back to testcontainers when `INTEGRATION_DATABASE_URL` is not set, so Docker is required for those local runs.

## Makefile targets

```
make help         show target help
make cluster-up   create k3d cluster
make cluster-down destroy cluster
make dev          tilt up
make dev-stop     tilt down
make lock         regenerate uv.lock for every service
make test         pytest across all services
make lint         ruff + pyright across all services
make fmt          ruff format across all services
make build        docker build (production target) all services
make push         build and push all service images to the local registry
make obs-up       install kube-prometheus-stack + Loki + Tempo + OTel; requires Grafana and Loki passwords in env
make argocd-up    install ArgoCD + apply app-of-apps
make keda-up      install KEDA
make dashboards   recompile Jsonnet dashboards → Grafana ConfigMaps
make helm-lint    helm lint all charts
make cold-start   cluster + KEDA + observability, then tilt up
```

## Design decisions

This is a single-developer project, so decisions are documented as lightweight design notes rather than formal review records.

| Decision | Summary |
|----------|---------|
| [0001](docs/design-decisions/0001-stack-choices.md) | Python 3.14, FastAPI, SQLAlchemy 2, uv |
| [0002](docs/design-decisions/0002-queue-depth-hpa.md) | KEDA for worker queue-depth autoscaling |
| [0003](docs/design-decisions/0003-gitops-argocd.md) | ArgoCD app-of-apps, Tilt coexistence |
| [0004](docs/design-decisions/0004-observability-stack.md) | Loki, Tempo, OTel Collector, Grafana dashboards |
| [0005](docs/design-decisions/0005-chaos-portal.md) | Starlette + HTMX, NetworkPolicy annotation patch |
| [0006](docs/design-decisions/0006-ci-cd.md) | GitHub Actions, GHCR, testcontainers, pyright |

## Implemented scope

| Area | Deliverable |
|------|-------------|
| Foundation | Devcontainer, k3d cluster, service template, orders-api, chart template |
| Core services | auth-api, gateway, report-api, worker, seed script |
| Traffic | loadgen (Locust headless) |
| Resilience | HPA, KEDA worker autoscaling, PDB, NetworkPolicies |
| GitOps | ArgoCD dev auto-sync, staging manual-sync, app-of-apps |
| Observability | kube-prometheus-stack, Loki, Tempo, OTel, Grafana dashboards (Jsonnet) |
| Chaos | chaos-portal pod kill + NetworkPolicy partition toggle |
| CI/CD | GitHub Actions CI/CD, testcontainers integration tests, pyright |
| Documentation | README, architecture, design decisions, security posture notes |
