# Phase 09B — Durable Repositories

**Status:** VERIFIED — AWAITING CHECKPOINT COMMIT

## Implemented

- Replaced synchronous fallback-prone tenant/session PostgreSQL code with async
  tenant transactions that propagate database failures.
- Added durable session runtime-plan fields and repository round trips.
- Added an async agent draft/version repository and made agent routes plus
  session compilation accept either the local test repository or durable async
  repository.
- Added an RLS-safe API-key authentication function and async key manager. Raw
  API keys are returned once; only SHA-256 hashes are written.
- Added a PostgreSQL encrypted-secret repository, async vault operations, and
  async provider-chain credential resolution.
- Added durable async audit writes and tenant audit queries.
- Control-plane and worker lifespans open and close the shared async pool in
  durable environments. Protected environments cannot select memory fallback.

## Verification

```text
pytest tests/db tests/auth tests/security/test_durable_secrets.py \
  tests/security/test_provider_credentials.py tests/agents \
  tests/providers/test_provider_routing.py \
  tests/providers/test_session_provider_binding.py \
  tests/e2e/test_published_agent_runtime.py \
  tests/hardening/test_h3_persistence.py -q
100 passed, 1 skipped, 1 warning
```

No live database, provider, telephony, or paid service was used.

## Operational gate

Apply migrations 019 and 020 to a disposable database before deployment. A
shared migration target still requires separate explicit authorization.
