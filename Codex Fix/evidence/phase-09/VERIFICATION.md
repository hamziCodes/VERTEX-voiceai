# Phase 09 Verification — Durable State, Admission, and Usage

**Date:** 2026-10-23

**Branch:** `wavia-fixv1`

**Base:** `51e8c87`

## Implementation commits

- `6a0d6f0` — async PostgreSQL pool, migration integrity, RLS, pgvector image.
- `8b6cc8c` — durable tenant/session/config/key/secret/audit repositories.
- `b439437` — atomic Redis session admission leases.
- `6ef7c69` — idempotent usage ledger and durable quota queries.
- `54207a1` — exact provider-reported LLM token metering.
- `cf16256` — disposable PostgreSQL and Redis verification gates.
- `ec7fa15` — committed migration transactions and Windows/live-test fixes.

## Automated evidence

```text
focused Phase 09D tests: 18 passed
broader Phase 09 regression set: 80 passed, 1 skipped
LLM usage/tool compatibility: 26 passed
full forced-offline suite after live-found fixes: 692 passed, 3 skipped, 2 warnings
disposable PostgreSQL/Redis integration: 2 passed
plan integrity: OK — 36 phases, tests, and trackers verified
compileall: exit 0
changed-file Ruff F/B scan: passed
migration discovery: 001 through 021, unique and ordered
protected paths changed: none
```

Two skips are the new disposable PostgreSQL/Redis gates and one is the existing
live database gate. The warnings are from deliberately short JWT values in a
negative authentication test.

## Proven offline contracts

- tenant DB work uses transaction-local `app.tenant_id`;
- migration names are unique and checksums fail closed;
- production repositories do not silently fall back to memory;
- Redis lease acquisition is atomic, expiring, idempotent, and fail closed;
- session mint uses persisted quota limits and Redis active counts;
- duplicate usage event keys produce one ledger row;
- STT, TTS, agent, telephony, and provider-reported LLM usage have stable units
  and retry-safe event keys;
- `/v1/usage` reads real monthly ledger totals.

## Disposable infrastructure evidence

The final run on 2026-10-23 proved migration execution, pgvector,
unprivileged RLS, restart persistence, duplicate usage idempotence, migration
idempotence, and real Redis contention/expiry/double release: `2 passed`.

The verification process found and corrected two issues before sign-off:

- Psycopg async tests now select a compatible event loop on Windows.
- Owned migration connections use autocommit so the advisory-lock transaction
  cannot roll back otherwise successful per-migration transactions at close.

The disposable containers and network were removed after the passing run.

No shared migration, live provider request, telephony call, deployment, or
paid provider action was performed. Shared staging migration requires separate
approval.
