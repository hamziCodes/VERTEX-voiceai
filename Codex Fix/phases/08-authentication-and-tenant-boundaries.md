# Phase 08 — Authentication and Tenant Boundaries

**Status:** SPLIT — 08A/08B VERIFIED, AWAITING COMMIT; 08C/08D NOT STARTED

**Goal:** Authenticate every management operation, derive tenant/role from trusted identity, and bind mint/session tokens to authorized tenants and agents.

**Depends on:** Phase 06. May run parallel with Phase 07.

**Audit coverage:** A01, A03, I04, I06 auth part, I08 auth part.

## Human gate before implementation

H08 was resolved on 2026-10-22. Dashboard identity uses a provider-neutral
external OIDC boundary; SDK/server management uses scoped tenant API keys.
Session JWT and mint/replay hardening remain 08C.

## Files and interfaces

- Create: central FastAPI auth dependency returning `AuthContext(subject_id, tenant_id, roles, scopes, key_id)`.
- Modify: all agent, knowledge, extraction, alert, usage, audit, secret and telephony management routes.
- Modify: API key persistence/verification, HMAC mint, JWT issue/verify, nonce store.
- Test: route matrix, two-tenant attacks, nonce concurrency, token claims/reuse/refresh/revocation.

## Tasks

- [x] Inventory every registered route and declare auth/scopes/roles; make public health/docs choices explicit.
- [x] Ignore/reject caller tenant headers that disagree with AuthContext; pass context through services/repositories.
- [x] Persist hashed API keys with tenant, scopes, role, expiry/revocation and last-used metadata.
- [ ] Bind quick/signed mint to authenticated tenant and tenant-owned published agent.
- [ ] Replace nonce exists-then-set with atomic Redis SET NX + TTL and test concurrent replay.
- [ ] Require JWT tenant/agent/session/action/iat/exp plus issuer/audience/jti; define one-use/concurrent-socket and refresh/revocation policy.
- [ ] Disable demo mint in staging/production regardless of explicit flag; reject every shipped/default signing secret in non-development modes.
- [ ] Add rate/size limits and sanitized failures for auth endpoints.
- [ ] Test unauthenticated, wrong scope/role/tenant/agent, revoked/expired key, duplicate nonce, reused token, missing Redis, and forwarded-header spoofing.

## Verification

```powershell
python -m pytest tests/security tests/hardening/test_h1_auth_crypto.py tests/auth/test_route_matrix.py -q
```

Expected: zero unauthorized success in route matrix; atomic replay rejection; no caller-controlled tenant identity; safe boot failures outside development.

## Human verification

Hamzi reviews public-route list, roles, and chosen IdP/admin boundary. No real user provisioning or external IdP call without approval.

## Exit criteria

- All management routes have explicit tested auth.
- Mint and session tokens are tenant/agent bound.
- Demo escape hatches cannot activate in staging/production.
