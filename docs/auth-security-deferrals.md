# Auth security deferrals

The auth-api applies the current baseline controls:

- usernames and emails are trimmed and lowercased before storage and login
- account lockout is persisted on the user row after repeated failed logins
- registration enforces a 12-character password with lowercase, uppercase,
  digit, and symbol requirements
- passwords may not contain the normalized username or email local part

The following controls are intentionally deferred for this codebase.

## Compromised-password checks

**Deferred control:** online Have I Been Pwned range checks or a comparable
compromised-password service during registration.

**Why:** this requires outbound network access from auth-api, availability
policy for the dependency, timeout and failure-mode choices, and privacy review
for password hash-prefix lookups. Those choices belong with production
operating requirements, not the local demo baseline.

**Current control:** local password complexity and identity-substring rejection.

**Reconsider if:** auth-api is promoted beyond local/demo use or outbound
dependency policy is defined.

## IP-based login throttling

**Deferred control:** persistent IP or username-plus-IP throttling for unknown
users and distributed brute-force attempts.

**Why:** durable IP throttling needs a shared store and proxy trust policy for
client IP extraction. In this deployment the gateway already rate-limits
`/api/auth/token`, while auth-api owns account-level lockout for known users.

**Current control:** generic `401 Invalid credentials` for unknown users,
gateway token-route rate limiting, and DB-backed account lockout for known
users.

**Reconsider if:** auth-api is exposed without the gateway or receives a shared
rate-limit store.
