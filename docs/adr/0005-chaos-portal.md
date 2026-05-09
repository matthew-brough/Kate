# ADR-0005 — Chaos Portal Design

**Date:** 2026-04-27  
**Status:** Accepted

## Context

Phase 7 adds a chaos engineering facility: a web portal that lets developers trigger controlled
failures against the platform namespace to verify observability (Phase 6) and resilience
(Phase 4 HPA/PDB).  Two failure modes are required:

1. **Pod kill** — delete a named pod; the deployment controller restarts it; latency spikes and
   error rates in the Grafana dashboards should show the event.
2. **Network partition** — block all ingress to a service; downstream health-check alerts should
   fire; un-partition restores normal traffic.

## Decisions

### Starlette over FastAPI

The portal is a rendered web UI, not a REST API.  FastAPI's OpenAPI scaffolding, dependency
injection, and Pydantic models add no value here.  Starlette is lighter and its `Route` + Jinja2
`TemplateResponse` pattern is a direct fit.

### HTMX for interactivity

A full SPA (React, Vue) would be disproportionate for two interactive panels.  HTMX turns HTML
into the protocol: kill-pod POST returns a `<div>` fragment that replaces the pod table in place.
Zero client-side JavaScript, no build step.

The pod table auto-refreshes every 5 s (`hx-trigger="every 5s"`), so users can watch the
replacement pod appear without manual reloads.

### Network partition via NetworkPolicy annotation patch

Kubernetes NetworkPolicy is **allow-only** — there is no explicit deny rule.  A pod with any
matching NetworkPolicy can only receive the traffic that policy permits.  Each service in the
platform has an `{service}-allow-ingress` policy granting gateway access.

Partition approach: `PATCH` the allow-ingress policy to `ingress: []`, effectively denying all
inbound traffic.  The original rules are serialised to JSON and stored in the annotation
`chaos.kate.dev/original-ingress` on the same object.  Un-partitioning reads the annotation and
restores the rules.

Alternative considered: delete the allow-ingress policy and re-create it.  Rejected because it
requires storing state externally (ConfigMap, etcd key) and does not survive portal restarts.
The annotation approach is self-contained — state lives with the object being modified.

### Scoped Role over ClusterRole

The portal only needs to manipulate pods and NetworkPolicies in the `platform` namespace.  A
namespaced `Role` + `RoleBinding` is the least-privilege choice.  ClusterRole was considered for
simplicity but grants cluster-wide access, which is inappropriate for a chaos tool.

RBAC verbs granted:
- `pods`: `list`, `get`, `delete`
- `networkpolicies`: `list`, `get`, `patch`

`create` and `delete` on NetworkPolicies are intentionally excluded — the patch approach never
creates or deletes policies, only modifies them in place.

### Access pattern

The portal supports two explicit auth modes:

- `token` mode is the default chart behavior.  It requires a shared token and accepts it via
  `X-Chaos-Token`, `Authorization: Bearer`, or browser Basic auth.  Basic auth exists because a
  direct browser navigation cannot attach the custom header that the original implementation
  required.
- `dev` mode bypasses portal auth and is used by Tilt/local dev values.  The portal is still only
  reachable through the local dev exposure path (normally the Tilt port-forward), while Kubernetes
  RBAC and the server-side service allowlist continue to constrain what the portal can mutate.

### No OTel / no Prometheus metrics

The portal is a dev tool used sporadically; high-cardinality traces and counters add noise to the
platform dashboards without diagnostic value.  structlog JSON to stdout is sufficient.

### `readOnlyRootFilesystem: false`

uvicorn and the kubernetes client may write temporary files under some configurations.  The portal
is not a production service, so filesystem hardening is deferred.  `PYTHONDONTWRITEBYTECODE=1` is
set in the image to prevent `.pyc` creation.  A `/tmp` emptyDir volume is mounted regardless.

## Consequences

- Chaos-portal runs in the `platform` namespace alongside the services it targets.
- The partition annotation is the source of truth for active partitions; if the portal pod is
  deleted while a partition is active the annotation persists on the NetworkPolicy and is
  visible on next startup.
- NetworkPolicy partitioning only works when `networkPolicy.enabled: true` in the target
  service's dev-values — if the allow-ingress policy does not exist, `toggle_partition` raises
  `ValueError` with a clear error message.
- `CHAOS_SERVICES` env var configures the service list; defaults cover all Phase 2 services
  (`orders-api,auth-api,report-api,worker`).
