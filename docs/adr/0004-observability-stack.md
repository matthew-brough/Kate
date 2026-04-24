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

`prometheus-community/kube-prometheus-stack` bundles Prometheus, Grafana, node-exporter, and kube-state-metrics. The all-in-one chart avoids wiring datasources manually.

`serviceMonitorSelectorNilUsesHelmValues: false` makes Prometheus discover ServiceMonitors from all namespaces — required because service charts deploy to `platform` while Prometheus is in `observability`.

`enableRemoteWriteReceiver: true` allows Tempo's metrics generator to write span-derived RED metrics back into Prometheus (future enhancement).

### Logs: Loki + Promtail

Loki runs in single-binary mode (no object storage, no persistence) — appropriate for a local k3d portfolio cluster. Promtail is a DaemonSet that tails pod logs and pushes to Loki.

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
- ServiceMonitors are enabled in dev-values for all four HTTP services and Redis.
- Dashboard ConfigMaps are in `infra/observability/dashboards/` — update via `make dashboards` when panels change.
- Loki and Tempo data is ephemeral (no persistence) — restarts clear history. Acceptable for a local portfolio cluster.
