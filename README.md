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
# 1. Create k3d cluster (1 server + 2 agents, local registry, Traefik ingress)
make cluster-up

# 2. Build, deploy, and live-reload all services
tilt up

# 3. Install observability stack (separate terminal, one-time)
make obs-up

# Grafana:  kubectl -n observability port-forward svc/kube-prometheus-stack-grafana 3000:80
# Gateway:  http://kate.localhost  (via Traefik)
# Seed:     uv run python scripts/seed.py
```

Optional add-ons (run once after `cluster-up`):

```bash
make keda-up    # KEDA for worker queue-depth autoscaling
make argocd-up  # ArgoCD GitOps — app-of-apps for dev + staging
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
| [`ci.yml`](.github/workflows/ci.yml) | every push + PR | ruff · pyright · pytest · integration tests (INTEGRATION=1) |
| [`build.yml`](.github/workflows/build.yml) | push to `main` | docker build → push to GHCR |
| [`helm.yml`](.github/workflows/helm.yml) | every push + PR | helm lint · ct lint |

Integration tests spin up real Postgres containers via testcontainers; Docker is required to run them.

## Makefile targets

```
make cluster-up   create k3d cluster
make cluster-down destroy cluster
make dev          tilt up
make test         pytest across all services
make lint         ruff + pyright across all services
make build        docker build (production target) all services
make obs-up       install kube-prometheus-stack + Loki + Tempo + OTel
make argocd-up    install ArgoCD + apply app-of-apps
make keda-up      install KEDA
make dashboards   recompile Jsonnet dashboards → Grafana ConfigMaps
make helm-deps    helm dependency update all charts
```

## Architecture Decision Records

| ADR | Decision |
|-----|----------|
| [0001](docs/adr/0001-stack-choices.md) | Python 3.14, FastAPI, SQLAlchemy 2, uv |
| [0002](docs/adr/0002-queue-depth-hpa.md) | KEDA for worker vs prometheus-adapter |
| [0003](docs/adr/0003-gitops-argocd.md) | ArgoCD app-of-apps, Tilt coexistence |
| [0004](docs/adr/0004-observability-stack.md) | Loki vs Fluentbit, Tempo vs Jaeger, OTel Collector |
| [0005](docs/adr/0005-chaos-portal.md) | Starlette + HTMX, NetworkPolicy annotation patch |
| [0006](docs/adr/0006-ci-cd.md) | GitHub Actions, GHCR, testcontainers, pyright |

## Project phases

| Phase | Deliverable |
|-------|-------------|
| 1 | Devcontainer, k3d cluster, service template, orders-api, chart template |
| 2 | auth-api, gateway, report-api, worker, seed script |
| 3 | loadgen (Locust headless) |
| 4 | HPA, KEDA worker autoscaling, PDB, NetworkPolicies |
| 5 | ArgoCD GitOps — dev auto-sync, staging manual-sync, app-of-apps |
| 6 | kube-prometheus-stack, Loki, Tempo, OTel, Grafana dashboards (Jsonnet) |
| 7 | chaos-portal — pod kill + NetworkPolicy partition toggle |
| 8 | GitHub Actions CI/CD, testcontainers integration tests, pyright |
| 9 | README, architecture.md, ADR index |
