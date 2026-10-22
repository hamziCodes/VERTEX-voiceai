# Phase 08A/08B Verification — Management Authentication and Tenant Boundaries

**Date:** 2026-10-22

**Branch:** `wavia-fixv1`

**Pre-phase rollback checkpoint:** `c751e3e2da329fcc6060cf12c06c315e38acb174`

**State:** verified, uncommitted; explicit commit confirmation required

## Implemented boundary

- Management identities normalize into immutable `AuthContext` values from a
  scoped tenant API key or an injected OIDC provider.
- Authenticated tenant, subject, roles, and scopes drive authorization.
  Caller tenant/role headers cannot create identity or raise privilege.
- All agent, knowledge, extraction, alert, usage, audit, and secret-management
  routes require explicit permission and tenant ownership.
- API keys support hash-at-rest lookup, role/scope checks, expiry, revocation,
  safe metadata listing, and last-used tracking.
- Staging/production boot rejects the in-memory API-key store. Migration 016
  prepares the durable schema; the deployment must inject its database adapter.

## Automated evidence

Environment was forced offline with `UCVE_ENV=test`, mock providers enabled,
live providers disabled, and live DB tests disabled.

```text
pytest tests/auth -q
18 passed, 1 warning

pytest tests/auth tests/e2e/test_system_endpoints_e2e.py \
  tests/hardening/test_h1_auth_crypto.py tests/security -q
61 passed, 3 warnings

pytest -q --basetemp=hamza_local/pytest-phase8-20261022
644 passed, 1 skipped, 3 warnings

ruff check <Phase 08A/08B auth and route paths>
All checks passed

ruff check control_plane/app.py --select B008,F
All checks passed

python -m compileall -q control_plane tests/auth
exit 0

git diff --check
exit 0
```

The warnings are the existing Starlette TestClient deprecation warning and two
short test-only JWT key warnings. No live call, provider, IdP, database, or
telephony request was made.

## Covered attacks and failures

- missing credentials;
- tenant-header spoofing and cross-tenant path/body access;
- role-header escalation;
- wrong API-key scope or role;
- expired and revoked API keys;
- invalid key/tenant/role inputs;
- OIDC and API-key identities using the same tenant boundary;
- production/staging use of the in-memory key store.

## Deferred deliberately

- Phase 08C: mint ownership, JWT issuer/audience/JTI, one-use sockets, atomic
  nonce/replay behavior, refresh/revocation, and demo-mint production guards.
- Phase 08D: remaining rate/size hardening and operational integration.
- External IdP provisioning and durable database adapter/runtime proof require
  deployment infrastructure and do not use live services in this phase.

## Next exact action

Review the Phase 08A/08B diff. If Hamzi confirms, create one clean implementation
commit on `wavia-fixv1`. Ask separately before pushing. Do not begin Phase 08C.
