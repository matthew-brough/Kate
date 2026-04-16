# ADR-0002: Queue-Depth Autoscaling for the Celery Worker

**Status**: Accepted  
**Date**: 2026-04-16

---

## Context

The Celery worker processes report-generation tasks from a Redis list queue. Three autoscaling
approaches were evaluated for scaling worker replicas in response to load.

### Option 1 — CPU-based HPA (k8s built-in)

`autoscaling/v2` with `resource.cpu` metric. No extra dependencies.

**Problem**: CPU is the wrong signal for I/O-bound queue workers. A worker blocks on
`asyncio.sleep()` (simulating DB work) while consuming near-zero CPU. The HPA would never
trigger even with 50 queued tasks. CPU is only a useful signal if *compute* is the
bottleneck — here the bottleneck is *throughput per worker*, which is measured by queue depth.

### Option 2 — prometheus-adapter + custom HPA

Deploy [prometheus-adapter](https://github.com/kubernetes-sigs/prometheus-adapter) alongside
kube-prometheus-stack. Write a `custom.metrics.k8s.io` rule that exposes
`redis_list_length{listName="celery"}` as a k8s custom metric. The HPA then targets this
metric via `type: Pods` or `type: External`.

**Pros**: standard Kubernetes HPA API, same recruiter signal as built-in metrics.  
**Cons**: requires Prometheus + redis_exporter already running (Phase 6 dependency). Forces
Phase 4 to wait on Phase 6, or introduces forward-porting complexity.

### Option 3 — KEDA (Kubernetes Event-Driven Autoscaler)

[KEDA](https://keda.sh) is a CNCF project that adds a `ScaledObject` CRD. It reads the
trigger source directly — for Redis, it reads the queue list length in-process. Internally
KEDA creates a standard `HPA` object; the k8s control plane still does the actual scaling.

**Pros**: zero Prometheus dependency; operational in Phase 4; native Redis scaler;
supports scale-to-zero and per-trigger cooldowns; broadly adopted in production.  
**Cons**: additional controller to install; `ScaledObject` is not a first-party k8s resource.

---

## Decision

**KEDA** (Option 3).

The primary reason is operational ordering: KEDA works with only Redis running, which is
already a Phase 2 dependency. Prometheus-adapter would block Phase 4 on Phase 6 and introduce
a circular dependency between observable infrastructure and the services being observed.

KEDA's `ScaledObject` is more expressive than a CPU HPA for this use case:
- `listLength: 5` means "add one replica per 5 queued tasks"
- `cooldownPeriod: 30` prevents flapping after a burst drains
- `minReplicaCount: 1` avoids cold-start latency under steady loadgen traffic

When Prometheus is available (Phase 6), the dashboard can read the same Redis metric via a
recording rule — KEDA and Grafana use independent metric paths, so they do not conflict.

### Why not CPU HPA at all?

CPU HPA *is* used for the four HTTP API services (gateway, orders-api, auth-api, report-api).
For HTTP services, request rate and CPU are correlated: more requests → more CPU. For queue
workers they are not.

---

## Configuration

KEDA is installed via `infra/keda/bootstrap.sh` (`make keda-up`). The worker chart exposes:

```yaml
keda:
  enabled: true          # flip to false to fall back to idle deployment
  minReplicas: 1
  maxReplicas: 8
  cooldownPeriod: 30     # seconds after queue drains before scaling in
  redisAddress: "redis-master:6379"
  queueName: "celery"    # default Celery queue key in Redis
  targetListLength: "5"  # one replica per N queued tasks
```

The `ScaledObject` targets the `worker` Deployment. When queue depth is 0 the HPA keeps
`minReplicaCount: 1` so loadgen reports are processed without cold-start delay.

---

## Consequences

- `make keda-up` must run before enabling `keda.enabled: true` in chart values.
- The standard `hpa.enabled` flag on the worker chart remains `false`; KEDA owns the HPA.
- Phase 6 ADR-0006 documents the Grafana panel that visualises queue depth vs. replica count
  as a time-series overlay — the "headline screenshot" for this decision.
