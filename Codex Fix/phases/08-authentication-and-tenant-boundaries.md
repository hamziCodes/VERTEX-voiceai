# Phase 08 — Authentication and Tenant Boundaries

**Status:** COMPLETE — READY FOR FINAL QA

**Goal:** Authenticate every management operation, derive tenant/role from trusted identity, and bind mint/session tokens to authorized tenants and agents.

**Depends on:** Phase 06. May run parallel with Phase 07.

**Audit coverage:** A01, A03, I04, I06 auth part, I08 auth part.

## Human gate before implementation

H08 was resolved on 2026-10-22. Dashboard identity uses a provider-neutral
external OIDC boundary; SDK/server management uses scoped tenant API keys.
Session JWT and mint/replay hardening were completed in 08C/08D.

## Files and interfaces

- Create: central FastAPI auth dependency returning `AuthContext(subject_id, tenant_id, roles, scopes, key_id)`.
- Modify: all agent, knowledge, extraction, alert, usage, audit, secret and telephony management routes.
- Modify: API key persistence/verification, HMAC mint, JWT issue/verify, nonce store.
- Test: route matrix, two-tenant attacks, nonce concurrency, token claims/reuse/refresh/revocation.

## Tasks

- [x] Inventory every registered route and declare auth/scopes/roles; make public health/docs choices explicit.
- [x] Ignore/reject caller tenant headers that disagree with AuthContext; pass context through services/repositories.
- [x] Persist hashed API keys with tenant, scopes, role, expiry/revocation and last-used metadata.
- [x] Bind quick/signed mint to authenticated tenant and tenant-owned published agent.
- [x] Replace nonce exists-then-set with atomic Redis SET NX + TTL and test concurrent replay.
- [x] Require JWT tenant/agent/session/action/iat/exp plus issuer/audience/jti; define one-use/concurrent-socket and refresh/revocation policy.
- [x] Disable demo mint in staging/production regardless of explicit flag; reject every shipped/default signing secret in non-development modes.
- [x] Add rate/size limits and sanitized failures for auth endpoints.
- [x] Test unauthenticated, wrong scope/role/tenant/agent, revoked/expired key, duplicate nonce, reused token, missing Redis, and forwarded-header spoofing.

## Verification

```powershell
python -m pytest tests/security tests/hardening/test_h1_auth_crypto.py tests/auth/test_route_matrix.py -q
```

Expected: zero unauthorized success in route matrix; atomic replay rejection; no caller-controlled tenant identity; safe boot failures outside development.

## Human verification

Hamzi reviews public-route list, roles, and chosen IdP/admin boundary. No real user provisioning or external IdP call without approval.

H08 was resolved on 2026-10-22. External IdP provisioning, durable API-key
storage wiring, and live deployment validation remain final deployment work.

## Exit criteria

- All management routes have explicit tested auth.
- Mint and session tokens are tenant/agent bound.
- Demo escape hatches cannot activate in staging/production.

## Result — 2026-10-22

- 08A/08B committed as `bf52744`; 08C/08D implementation committed as
  `f2f861e` on `wavia-fixv1`.
- The final forced-offline suite passed with 659 tests and one skip. The final
  focused auth/hardening suite passed 56 tests.
- Plan integrity, compile, targeted Ruff, diff, forbidden-scope, and
  credential-pattern checks passed without live traffic or paid services.
