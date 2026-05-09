# Security posture: intentional non-closures

This file lists places where the platform deliberately does **not** apply a
hardening control that one might expect, and explains why. If you're auditing
this codebase and find one of these, the answer to "why isn't this locked
down?" is below.

Each entry: what's left open, why, and what the actual control is.

---

## Postgres pods: `readOnlyRootFilesystem` is **not** set

**Where:** `charts/{auth-api,orders-api,report-api}/templates/postgresql.yaml`,
container `securityContext`.

**Why:** the official `postgres:17-alpine` image writes outside the data
volume — to `/run/postgresql` (Unix socket), `/tmp` (temp files for some ops),
and during initdb to additional locations under `/var/lib/postgresql`. Setting
`readOnlyRootFilesystem: true` would require a non-trivial fan-out of
`emptyDir` mounts (`/run/postgresql`, `/tmp`, etc.) to keep postgres running.
We're not paying that complexity for this codebase.

**What is set:** `runAsNonRoot: true` (uid 70 / postgres user on Alpine),
`fsGroup: 70`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation:
false`, `capabilities.drop: [ALL]`. Those collectively address the same
threat model — root escape and capability abuse — without breaking postgres'
expected I/O paths.

**Reconsider if:** we move to a postgres image that documents a clean
read-only-rootfs setup, or if compliance requires it.

---

## chaos-portal NetworkPolicy: `ingress: - {}` (allow from anywhere)

**Where:** `charts/chaos-portal/templates/networkpolicy.yaml`, the
`*-allow-ingress` policy.

**Why:** the chaos-portal UI is accessed in dev via `kubectl port-forward`,
which routes through the kubelet's pod port (not from another pod), so a
`from: { podSelector: ... }` ingress rule would block dev access entirely.
For real env exposure the call site is the Ingress controller, which sits
outside this chart's NetworkPolicy scope.

**What is set:** in the default `token` mode, `TokenAuthMiddleware` rejects
every non-health request without a matching shared token. The token may be sent
as `X-Chaos-Token`, `Authorization: Bearer`, or browser Basic auth; comparisons
use timing-safe `hmac.compare_digest`. The token lives in `.env`/Secret and the
app refuses to start in token mode if unset. Local Tilt dev uses explicit
`dev` mode so the UI can be reached through its port-forward without browser
header injection. Kill/partition routes additionally validate path-params
against an in-app `SERVICES` allowlist (so a stolen token still can't kill
arbitrary pods).

**Reconsider if:** the portal stops being port-forward-only and gets a stable
in-cluster client (e.g. an internal dashboard) — then `from: { podSelector }`
becomes meaningful and should be added.

---

## chaos-portal RBAC: `pods.delete` is **not** scoped by `resourceNames`

**Where:** `charts/chaos-portal/templates/role.yaml`, the `pods` rule.

**Why:** k8s pod names are dynamic (`<deployment>-<rs>-<pod>`), so a
hardcoded `resourceNames` list would be permanently wrong. RBAC has no
prefix/glob support to express "any pod whose name starts with `orders-api-`".

**What is set:** the in-app allowlist in
`services/chaos-portal/src/app/main.py:kill_pod` rejects with 400 unless the
pod name prefix-matches an entry in `SERVICES`. So even if RBAC permits the
delete at the API server, the app refuses to issue it. NetworkPolicy `patch`
*is* scoped by `resourceNames` (those names are deterministic:
`<service>-allow-ingress`).

**Reconsider if:** k8s grows resourceName-prefix matching, or we adopt a
policy engine (Kyverno, Gatekeeper) that can enforce the prefix shape at the
API server. Until then the app code is the load-bearing control.

---

## chaos-portal `readOnlyRootFilesystem: false` on the app container

**Where:** `charts/chaos-portal/templates/deployment.yaml`.

**Why:** the kubernetes Python client writes a config cache under
`$HOME` / `/.kube`, and Jinja2's auto-reload (when running `--reload`-style)
also writes intermediate templates. `tmpfs`-mounting both is more moving
parts than the chaos-portal's risk profile justifies.

**What is set:** `runAsNonRoot`, `runAsUser: 1001`, `fsGroup: 1001`,
`drop: [ALL]`, `allowPrivilegeEscalation: false`, `seccompProfile:
RuntimeDefault`, plus the in-app token + allowlist controls described above.

**Reconsider if:** chaos-portal becomes anything beyond a dev/demo tool.
