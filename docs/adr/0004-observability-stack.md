# ADR-0004: Observability stack — metrics, logs, and traces

**Date:** 2026-04-24  
**Status:** Accepted

## Context

Phase 6 adds full-stack observability to the Kate platform. Every service already instruments:

- **Metrics** — `prometheus-fastapi-instrumentator` exposes `/metrics` (HTTP request rate, error rate, latency histograms)
- **Structured logs** — `structlog` emits JSON with `trace_id` / `span_id` fields
- **Traces** — `opentelemetry-sdk` + OTLP exporter; disabled by default (`APP_OTLP_ENABLED=false`), enabled in dev after `make obs-up`

The goal is a single `make obs-up` command that installs the full collection and visualization stack in a dedicated `observability` namespace, without touching application code.

## Decisions

### Metrics: kube-prometheus-stack

`prometheus-community/kube-prometheus-stack` bundles Prometheus, Alertmanager, Grafana, node-exporter, and kube-state-metrics. The all-in-one chart avoids wiring datasources manually.

`serviceMonitorSelectorNilUsesHelmValues: false` makes Prometheus discover ServiceMonitors from all namespaces — required because service charts deploy to `platform` while Prometheus is in `observability`.

`enableRemoteWriteReceiver: true` allows Tempo's metrics generator to write span-derived RED metrics back into Prometheus (future enhancement).

Alertmanager is enabled so platform alerts have a first-class runtime target. External receivers (PagerDuty, Slack, email, webhooks) are intentionally deferred until the operational owner and escalation policy are chosen.

### Logs: Loki + Promtail

Loki runs in single-binary mode with local filesystem storage — appropriate for a local k3d portfolio cluster. Promtail is a DaemonSet that tails pod logs and pushes to Loki through the in-cluster Loki gateway.

Loki multi-tenancy is enabled. The gateway enforces basic auth using a Kubernetes secret-generated htpasswd file, then maps the authenticated user to `X-Scope-OrgID`. Promtail and Grafana use the shared `kate` tenant; the password is supplied through `LOKI_TENANT_PASSWORD` at bootstrap time and is never committed to values files.

Promtail's pipeline extracts `trace_id` and `span_id` from structlog JSON output and promotes them to Loki stream labels. This powers Grafana's derived-fields feature: clicking a trace ID in a log line jumps directly to the matching trace in Tempo.

Alternative considered: **Fluentbit** — lighter but requires more manual Loki output config. Promtail's native Grafana integration was the deciding factor.

### Traces: Tempo

Tempo stores traces locally (no S3/GCS dependency). Services send OTLP gRPC to the OTel Collector (port 4317 in `observability`), which forwards to Tempo. Routing via Collector rather than direct-to-Tempo lets us add processors (sampling, attribute enrichment) without touching service config.

Alternative considered: **Jaeger** — heavier operator footprint, Grafana datasource requires a separate plugin. Tempo's native Grafana datasource and simpler storage model won.

### Grafana cross-datasource linking

Three linking directions are configured:

| From | To | Mechanism |
|------|----|-----------|
| Logs (Loki) | Traces (Tempo) | `derivedFields` on `trace_id` field |
| Traces (Tempo) | Logs (Loki) | `tracesToLogsV2` with `filterByTraceID` |
| Traces (Tempo) | Service map | `nodeGraph.enabled` (trace-level view) |

Grafana admin credentials come from the `grafana-admin` Kubernetes secret created by `infra/observability/bootstrap.sh`. The chart no longer ships a default `admin/admin` credential.

### Dashboards: Jsonnet → ConfigMap sidecar

Dashboards are authored in Jsonnet (`dashboards/*.jsonnet`) using a minimal local library (`dashboards/lib/grafana.libsonnet` — no external jb deps). Pre-compiled JSON is committed as ConfigMaps under `infra/observability/dashboards/`. The Grafana sidecar picks them up via the `grafana_dashboard: "1"` label.

`make dashboards` recompiles Jsonnet → JSON and re-applies the ConfigMaps (requires `jsonnet` in `$PATH`).

Two dashboards:
- **platform-overview** — RPS, error rate, P99/P50 latency, pod count, CPU
- **worker-queue** — Celery queue depth (via `redis_list_length`), worker replicas, report request rate, memory

### OTel env vars in dev

All four FastAPI services (`orders-api`, `auth-api`, `gateway`, `report-api`) have `APP_OTLP_ENABLED: "true"` and `APP_OTLP_ENDPOINT: "otel-collector.observability.svc.cluster.local:4317"` added to their `ci/dev-values.yaml`. The worker (Celery) is excluded — it would need `opentelemetry-instrumentation-celery`, a future enhancement.

## Consequences

- `make obs-up` must be run after `make cluster-up` (before or after `make dev` — the observability namespace is independent).
- `make obs-up` requires `GRAFANA_ADMIN_PASSWORD` and `LOKI_TENANT_PASSWORD`; local generated passwords are acceptable for development.
- ServiceMonitors are enabled in dev-values for all four HTTP services and Redis.
- Dashboard ConfigMaps are in `infra/observability/dashboards/` — update via `make dashboards` when panels change.
- Loki access is restricted to the authenticated gateway path for Grafana and Promtail. Direct Loki pod ingress is limited to Loki's own gateway/memberlist traffic by NetworkPolicy.
- Loki and Tempo data uses local cluster storage. This is acceptable for a local portfolio cluster; object storage and retention policy design remain deferred for a production environment.
