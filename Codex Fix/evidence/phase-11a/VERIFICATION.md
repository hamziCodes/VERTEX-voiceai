# Phase 11A Verification Evidence

**Date:** 2026-10-26
**Implementation commit:** `2287665` — truthful durable call lifecycle
**Scope:** offline/local verification only; no live calls, provider requests, cloud storage, shared database migration, deployment, or paid traffic.

## Delivered behavior

- A tenant-scoped call record is created once when a web or telephony session is admitted and finalized once with actual UTC timestamps, disposition, provider snapshot, metering snapshot, and end reason.
- Redacted user and played-assistant turns are persisted incrementally with stable ordinals. Duplicate writes are idempotent; conflicting ordinal reuse fails closed.
- Recording is off by default and cannot gain an object reference without checksum, duration, channel, and region evidence. A consented request with no active recorder is stored as `failed/recording_capture_unavailable`, never as a fabricated recording or `not_requested`.
- PostgreSQL enforces tenant/session uniqueness, turn uniqueness, tenant RLS with `WITH CHECK`, finalization immutability, recording-state/evidence consistency, and explicit legacy-data preflight failures.
- Local/test fixtures may derive deterministic UUIDs from short identifiers. Protected environments continue to reject invalid tenant, agent, and session UUIDs.

## Test evidence

### Test-driven safeguards

- Recording model/state mismatch and legacy duplicate-session migration checks failed before implementation, then passed.
- Requested-but-unavailable recording and database evidence-consistency checks failed before implementation, then passed.

### Focused suite

```powershell
py -3.12 -m pytest tests/post_call tests/db/test_phase11_post_call_migration.py voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py -q -p no:cacheprovider --basetemp C:\tmp\wavia-phase11a-invariant-20261026-01
```

Result: **18 passed**.

### Complete forced-offline suite

```powershell
py -3.12 -m pytest -q -p no:cacheprovider --basetemp C:\tmp\wavia-phase11a-exact-full-20261026-01
```

Result: **811 passed, 8 skipped, 2 known short-test-HMAC warnings**. No live-provider flags were enabled.

### Disposable PostgreSQL integration

A generated password and ignored temporary Compose file started local `pgvector/pgvector:pg16` and Redis containers on ports `45432` and `46379`. The command set `RUN_LIVE_DB_TESTS=1`, `RUN_LIVE_PROVIDERS=0`, and ran:

```powershell
py -3.12 -m pytest tests/db/test_phase11a_live_integration.py -q -p no:cacheprovider --basetemp C:\tmp\wavia-phase11a-db-20261026-03
```

Result: **1 passed**. This covered migrations, restart-safe idempotency, incremental turns, immutable duplicate finalization, tenant RLS, recording-evidence round-trip, direct-SQL constraint rejection, and migration reapplication. Containers, network, volumes, temporary Compose file, and environment variables were removed afterward.

The active Python 3.12 user environment was missing `psycopg-pool`; version `3.3.3`, already declared by `pyproject.toml` and locked by `uv.lock`, was restored before the successful run.

## Static and integrity gates

- Ruff check: **passed** for all 15 touched Python files/scopes.
- Ruff format check: **15 files already formatted** after deterministic formatting.
- Scoped strict mypy with imported modules skipped: **no issues in 4 source files**.
- Python compilation: **passed** for `post_call`, database repositories, worker, and Phase 11 tests.
- Plan integrity: **OK — 36 phases, tests, and trackers verified**.
- `git diff --check`: **passed**.
- Staged review: **16 files**, no `.github/workflows`, `.env`, raw key file, secret-shaped literal, or unrelated path staged.

## Known boundaries

- Phase 11A records truthful lifecycle state but does not capture or upload audio. Object storage arrives in 11D; until then a requested recording ends in an explicit unavailable failure.
- Durable outbox jobs, extraction, summaries, and human review are Phase 11B.
- Webhook delivery is Phase 11C. Retention execution, legal hold, erasure, and final privacy close are Phase 11D.
- Existing databases containing legacy recording URIs or duplicate tenant/session rows must be reviewed before migration 024; the migration stops with a named resolution error instead of guessing metadata.

## Next exact action

Begin Phase 11B with failing tests for transactional post-call outbox creation, lease/retry/DLQ behavior, evidence-backed extraction and summaries, and authenticated human-review gates. Do not dispatch webhooks or external actions in 11B.
