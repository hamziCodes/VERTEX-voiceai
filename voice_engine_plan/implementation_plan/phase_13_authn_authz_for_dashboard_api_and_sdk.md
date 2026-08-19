# Phase 13: AuthN/AuthZ for Dashboard, API, and SDK

## 1. Executive Summary & Core Logic

Define authentication and role-based access for three surfaces: (1) tenant host backends calling session mint via HMAC, (2) dashboard/studio users managing agents, (3) third-party SDK integrators using API keys. Generalizes habiba mint gates (`legacy_codebases/habiba-sdk-agent/control_plane/mint.py` — HMAC, replay window, quota, IDOR guard) and awaazlabs Clerk org model (`legacy_codebases/awaazlabs/AwaazLabs-frontend-from-github/` — **reference only**; Clerk is not a runtime dependency per blueprint File 01). Fixes legacy failures: v3/MULTI unauthenticated WS (AUDIT_01/03), awaazlabs fail-open Retell secret check (AUDIT_02 §6), habiba in-memory rate limiter (AUDIT_04 §5 — `control_plane/app.py` `_rate_limited`).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| HMAC server-to-server mint (habiba) | Zero secrets in browser SDK |
| JWT session tokens TTL 120 s | habiba `mint.py` `TTL_SEC = 120` |
| Redis nonce replay cache | Replaces habiba 60 s in-memory window — Phase 01 blueprint File 01 §3.3 |
| API keys (hashed) for SDK/REST | Standard B2B integrator pattern |
| RBAC: `platform_admin`, `tenant_admin`, `tenant_editor`, `tenant_viewer`, `compliance_admin` | Maps to awaazlabs role-gated PHI actions |
| Built-in auth + OIDC hook interface | Enterprise SSO later without Clerk lock-in |

**Reference docs:** blueprint File 08 §2 OpenAPI security schemes; habiba `control_plane/app.py`; OWASP API Security Top 10.

## 3. What / How / Why

- **What:**
  - **Mint auth (HMAC):** `POST /v1/session` — signature over `{tenant_id}.{ts}.{nonce}.{agent_id}` (habiba `mint.py` `expected_signature()`), replay window 60 s, single-use nonce in Redis, origin allowlist from Phase 08 `tenants.allowed_origins`
  - **Session JWT:** scoped to one room/session; grants `roomJoin` only (habiba comment block lines 6–7)
  - **Dashboard auth:** **built-in** email/password + **`OIDCProvider` hook interface** for enterprise SSO (Auth0/Okta adapters plug in without replacing core auth)
  - **WS auth (sovereign plane):** short-lived JWT via **`?token=` query param on WSS only** — Phase 07 must redact this from logs/proxy access logs
  - **API keys:** `api_keys` table — prefix + hash; scopes: `session:mint`, `agent:read`, `agent:write`, `usage:read`; actor ID for Phase 12 audit
  - **RBAC middleware:** FastAPI dependency checks role × resource × action matrix
  - **Rate limiting:** Redis sliding window **120/min/tenant default** (habiba `control_plane/app.py` `RATE_LIMIT_PER_MIN`); overridable via Phase 14 quota config
  - **Protect Phase 07 `/metrics`:** bearer token required
- **How:** Control plane validates HMAC before any session row insert. Worker validates JWT on WS connect (Phase 17). Failed mint → Phase 12 `mint_rejections`. API key auth for headless integrators; keys rotatable with audit. Webhook endpoints (Phase 21) use HMAC signatures — fail closed if secret unset (fix awaazlabs `checkSecret` fail-open).
- **Why this approach:** Multi-tenant B2B requires defense in depth at mint boundary — habiba proved the shape. Clerk coupling rejected for voice path independence. Alternative: API key only — insufficient for browser studio without exposing keys.

## Deliverables

- `infra/db/migrations/007_auth_rbac.sql` — `users`, `memberships`, `api_keys`, `roles`
- `control-plane/auth/__init__.py`
- `control-plane/auth/hmac_mint.py` — port habiba verify logic
- `control-plane/auth/jwt.py` — issue/validate session + dashboard JWTs
- `control-plane/auth/api_keys.py`
- `control-plane/auth/rbac.py` — permission matrix
- `control-plane/auth/rate_limit.py` — Redis-backed limiter
- `control-plane/auth/oidc_hook.py` — `OIDCProvider` protocol + stub
- `control-plane/auth/middleware.py`
- `control-plane/routes/session.py` — `POST /v1/session`, `/v1/session/refresh`
- `core/redis/nonce_store.py` — replay cache

## 4. Compute & Resource Profile (if applicable)

HMAC verify: < 1 ms. Redis nonce check: < 2 ms LAN. JWT sign/verify: < 0.5 ms. Rate limiter: O(1) Redis INCR. Redis recommended: 256 MB instance for nonce + rate limit at 1000 tenants.

## 5. Compliance Notes (if applicable)

Auth events (`login`, `api_key_create`, failed mint) → Phase 12 audit. HIPAA: enforce MFA for `tenant_admin` `[LATER]` — flag in Phase 10 policy. Session JWT must not embed provider API keys. GDPR: user delete cascades membership; audit log retains actor_id as pseudonymized reference.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Dashboard auth:** built-in + OIDC hook interface for enterprise SSO.
2. **WS auth:** short-lived `?token=` on WSS; Phase 07 redaction required.
3. **Rate limit:** 120/min/tenant default; overridable via Phase 14.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py`
- **Asserts:** valid HMAC mint succeeds; replay nonce fails; expired signature fails; wrong agent_id IDOR blocked; RBAC denies viewer write; rate limit 429; `/metrics` rejects unauthenticated; API key scope enforced; WS rejects missing/invalid token.
- **Pass threshold:** 100% auth matrix tests; zero mint without valid HMAC in integration test.
- **Latency target:** mint auth path < 15 ms p99 excluding DB.
