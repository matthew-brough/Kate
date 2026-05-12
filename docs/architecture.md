# Architecture

## Service graph

```
Browser / loadgen
        │
        ▼
   ┌─────────┐         JWT secret (shared env var)
   │ gateway │ ─────────────────────────────────────┐
   └────┬────┘                                      │
        │ /api/auth/*   /api/orders/*   /api/reports/*
        │
   ┌────┴──────────────────────────────┐
   │                                   │
   ▼           ▼                       ▼
┌──────────┐ ┌────────────┐     ┌───────────────┐
│ auth-api │ │ orders-api │     │  report-api   │
│ Postgres │ │  Postgres  │     │   Postgres    │
└──────────┘ └────────────┘     └───────┬───────┘
                                        │ Celery enqueue
                                        ▼
                                  ┌───────────┐
                                  │   Redis   │ ◄── KEDA ScaledObject
                                  └─────┬─────┘
                                        │ Celery consume
                                        ▼
                                  ┌──────────┐
                                  │  worker  │
                                  │ Postgres │  (shared report-api DB)
                                  └──────────┘
```

## Request flow — authenticated order creation

1. `POST /api/orders` hits gateway.
2. Gateway decodes the `Authorization: Bearer <jwt>` locally (no auth-api round-trip).
3. Gateway injects `X-User-Id` header and proxies to `orders-api:8000/orders`.
4. orders-api writes to its own Postgres; returns 201.
5. Structlog emits a JSON log line including `trace_id`; Promtail ships it to Loki.
6. OTel SDK emits a span to otel-collector → Tempo.
7. Grafana cross-links log ↔ trace via the `trace_id` field.

## Request flow — async report

1. `POST /api/reports` → gateway → report-api.
2. report-api creates a `Report(status=pending)` row, calls `celery_app.send_task(...)`.
3. Returns 202 with the report UUID.
4. Client polls `GET /api/reports/{id}` until status changes.
5. Worker dequeues from Redis, sleeps 2-8 s, writes `COMPLETED` or `FAILED` to Postgres.

## Networking

Each service has three NetworkPolicies when `networkPolicy.enabled` is true:

| Policy | Effect |
|--------|--------|
| `{svc}-deny-all` | Deny all ingress + egress (baseline) |
| `{svc}-allow-ingress` | Allow ingress from gateway on port 8000 |
| `{svc}-allow-egress` | Allow egress to DNS (53), Postgres (5432), OTLP (4317) |

gateway's allow-ingress policy permits all sources (it is the edge).  
worker has egress only (no HTTP server).

The chaos-portal patches `{svc}-allow-ingress` to inject network partitions.

## Data stores

| Store | Used by | Notes |
|-------|---------|-------|
| orders Postgres | orders-api | Bitnami sub-chart; `asyncpg` driver |
| auth Postgres | auth-api | Bitnami sub-chart; bcrypt passwords, UUID PKs |
| report Postgres | report-api + worker | **shared** sub-chart; worker uses NullPool to avoid asyncpg connection issues after Celery fork |
| Redis | worker (broker), KEDA | Bitnami sub-chart; `redis_list_length{key="celery"}` scraped for queue depth |

## Observability stack

```
services → OTel Collector:4317 → Tempo (traces)
                                ↕ cross-link via trace_id
        → Promtail → Loki (logs)

services → ServiceMonitor → Prometheus → Grafana dashboards
Redis    → redis_exporter → Prometheus → worker-queue dashboard
```

All components live in the `observability` namespace.  
`serviceMonitorSelectorNilUsesHelmValues: false` on Prometheus allows scraping ServiceMonitors
from the `platform` namespace without needing a ClusterRole.

Grafana derived fields: Loki regex `"trace_id":"([0-9a-f]{32})"` links to Tempo;  
Tempo `tracesToLogsV2` links back to Loki filtered by trace ID.

## GitOps (ArgoCD)

```
gitops/root-dev.yaml  →  gitops/apps/dev/   (auto-sync, namespace: platform)
gitops/root-staging.yaml → gitops/apps/staging/ (manual sync, namespace: platform-staging)
```

App-of-apps pattern: two root Applications own per-service Applications.  
Tilt and ArgoCD share the same cluster; do not run both against the same namespace
simultaneously (selfHeal would revert Tilt changes).

## Autoscaling

| Service | Mechanism | Signal |
|---------|-----------|--------|
| orders-api, auth-api, gateway, report-api | HPA (autoscaling/v2) | CPU 70% |
| worker | KEDA ScaledObject | `redis_list_length{key="celery"}` — 1 replica per 5 tasks, max 8 |

## Directory structure

```
Kate/
├── services/
│   ├── _template/          canonical FastAPI service (fork, do not deploy)
│   ├── orders-api/
│   ├── auth-api/
│   ├── gateway/
│   ├── report-api/
│   ├── worker/
│   ├── loadgen/            Locust headless, ~5 VUs
│   └── chaos-portal/       Starlette + HTMX chaos engineering portal
├── charts/
│   ├── _template/          reference chart with resilience templates feature-flagged
│   └── {service}/          one chart per service; postgresql sub-chart where needed
├── gitops/
│   ├── root-{dev,staging}.yaml
│   └── apps/{dev,staging}/ one Application manifest per service
├── infra/
│   ├── bootstrap.sh        k3d cluster + Traefik + registry
│   ├── keda/               KEDA install
│   ├── argocd/             ArgoCD install + root app-of-apps
│   └── observability/      kube-prometheus-stack, Loki, Promtail, Tempo, OTel
├── dashboards/             Jsonnet source for Grafana dashboards
├── docs/design-decisions/  0001-0006 structured design decision notes
├── Makefile
└── Tiltfile
```
