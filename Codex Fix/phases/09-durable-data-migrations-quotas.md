# Phase 09 — Durable Data, Migrations, Quotas, and Usage

**Status:** NOT STARTED

**Goal:** Replace process-local production state with one consistent PostgreSQL/pgvector and Redis architecture, correct RLS, atomic admission, and an idempotent usage ledger.

**Depends on:** Phases 07–08.

**Audit coverage:** A02 durability, I02, I03, I05, I06 state, I07, P04 persistence.

## Human gate before implementation

Resolve H09. Never run migrations against a shared database without a separate explicit approval naming that target.

## Files and interfaces

- Standardize one async DB driver/pool and placeholder convention.
- Modify: `core/db/*`, repositories, app lifespans, Redis stores, migrations/runner, compose database image.
- Create: durable AgentConfig/APIKey/Secret/SessionPin/Usage/Admission repositories and integration tests.

## Tasks

- [ ] Choose async psycopg or asyncpg and refactor hot async paths away from synchronous connections.
- [ ] Standardize RLS variable to one name and set it transaction-locally for every tenant transaction; use an unprivileged application role.
- [ ] Use a pgvector-capable image/extension and correct vector query/column types.
- [ ] Renumber duplicate migration IDs; add lock, checksum, one transaction per migration, crash-safe bookkeeping and non-destructive upgrade path.
- [ ] Move agent versions/pins, API keys, encrypted credentials, sessions, audit and usage from local dictionaries to repositories; retain in-memory implementations only as explicit tests.
- [ ] Implement atomic Redis admission lease with TTL/heartbeat/release/reconciliation; acquisition rolls back on mint failure.
- [ ] Enforce concurrent/monthly limits from durable counts at worker admission, not caller-supplied zeros.
- [ ] Record idempotent STT seconds, LLM tokens, TTS units, agent/telephony seconds and provider correlation; query real totals.
- [ ] Test fresh install, upgrade from every supported migration state, crash between schema/bookkeeping, cross-tenant RLS, restart/multi-process, abandoned mint expiry, double release and duplicate usage event.

## Verification

```powershell
python -m pytest tests/hardening/test_h3_persistence.py tests/db tests/metering -q
```

Add disposable Compose fresh-install/upgrade commands at execution time. Expected: non-superuser tenant isolation, pgvector query works, state survives restart, concurrent reservation never exceeds limit, duplicate usage is idempotent.

## Human intervention

Hamzi may run the disposable DB/Redis command and return sanitized summaries. Shared staging migration remains a later approval.

## Exit criteria

- Production defaults do not use process-local repositories.
- RLS and migration recovery are proven in disposable infrastructure.
- Quota/admission/usage agree across processes and teardown.
