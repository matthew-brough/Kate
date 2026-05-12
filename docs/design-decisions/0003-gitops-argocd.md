# Design Decision 0003: GitOps with ArgoCD App-of-Apps

**Date:** 2026-04-20  
**Status:** Current  
**Scope:** GitOps topology and local Tilt coexistence

## Context

The platform has a GitOps promotion flow. Services need to be deployed to a `dev`
environment (auto-sync on every merge) and a `staging` environment (manual promotion
gates). The tooling must:

- Reconcile cluster state from Git without imperative `helm upgrade` calls
- Provide a UI for visibility into sync status and diff
- Coexist with Tilt for the local inner dev loop (Tilt manages the day-to-day build-reload cycle; ArgoCD manages the GitOps state of declared environments)

## Options considered

| Option | Notes |
|--------|-------|
| **Flux v2** | Pull-only, HelmRelease CRD, lighter footprint. No built-in UI; requires separate Weave GitOps or Grafana plugin for visibility. Stronger GitOps purity (no push model). |
| **ArgoCD** | App-of-apps pattern, built-in UI, wide adoption. `Application` CRD gives per-service sync status at a glance. CLI (`argocd`) enables scriptable promotion. |

## Decision

**ArgoCD with app-of-apps.**

Two root Applications:

| Root app | Watches | Sync mode |
|----------|---------|-----------|
| `kate-dev` | `gitops/apps/dev/` | Automated (prune + selfHeal) |
| `kate-staging` | `gitops/apps/staging/` | Manual |

Each directory contains one `Application` manifest per service. Each child Application points to `charts/<service>` with an environment-specific `ci/<env>-values.yaml`.

## Image tag promotion flow

1. CI builds and pushes `ghcr.io/<owner>/kate-<svc>:<git-sha>`.
2. Promotion is a source change to the service chart's environment values, normally
   `image.repository` and `image.tag` for the target environment.
3. Merge → ArgoCD detects OutOfSync on the `<svc>-staging` Application → operator clicks Sync (or `argocd app sync`).

Dev promotes automatically on every merge (no PR gate).

## Tilt coexistence

Tilt is the inner dev loop: it builds images locally from source and live-syncs Python files into running pods. ArgoCD manages the declared GitOps state of `dev` and `staging`. They don't fight because:

- Tilt targets the local registry (`registry.localhost:5001`) and the `platform` namespace directly via `kubectl apply`.
- ArgoCD's `selfHeal` would revert Tilt changes — **do not run both simultaneously against the same namespace.** Use Tilt (`make dev`) for active development and ArgoCD for environment reconciliation.

## Consequences

- All cluster state is declarative and auditable via Git history.
- Staging promotions require an explicit human action (PR merge + sync).
- `make argocd-up` must be run once after `make cluster-up`.
- KEDA (`make keda-up`) must still be run before enabling `keda.enabled: true` in dev-values.
