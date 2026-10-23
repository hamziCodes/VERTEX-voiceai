# Phase 09D — Usage Ledger and Durable Quotas

**Status:** COMPLETE — OFFLINE AND DISPOSABLE INFRASTRUCTURE VERIFIED

## Implemented

- Added an append-only PostgreSQL usage repository with tenant-scoped,
  idempotent event keys and provider/request correlation.
- Added migration `021_idempotent_usage_ledger.sql` for event keys, units,
  provider fields, metadata, indexes, and a nonnegative write constraint.
- Replaced caller-supplied monthly usage with durable ledger snapshots.
- Combined durable PostgreSQL quota limits with atomic Redis tenant lease
  counts at mint time.
- Changed `/v1/usage` to return persisted monthly totals, configured limits,
  and the current tenant lease count.
- Metered exact agent, STT-input, generated TTS, and telephony seconds.
- Added provider-reported LLM token metadata to the streaming contract and
  persisted one retry-safe token event per turn. No estimated tokens are
  written when a provider does not report usage.
- Added gated disposable PostgreSQL and Redis integration tests. Normal test
  runs cannot contact either service.

## Offline verification

```text
usage/admission/legacy quota contracts: 18 passed
persistence/control-plane/pipeline regressions: 80 passed, 1 skipped
LLM usage and tool-stream compatibility: 26 passed
final forced-offline repository suite: 692 passed, 3 skipped, 2 warnings
disposable PostgreSQL/Redis integration: 2 passed
focused Ruff F/B checks: passed
compileall: passed
plan integrity: OK — 36 phases, tests, and trackers verified
```

Two skips are the new disposable PostgreSQL/Redis gates and one is the existing
live database gate. The warnings are confined to a negative JWT test that
intentionally uses short test keys. Repository-wide Ruff still reports 45
pre-existing findings; the Phase 09 changed-file F/B scan passes.

## Human verification — disposable local stores

This test is local and makes no provider or telephony request. Docker may need
to download the public PostgreSQL/Redis images if they are not already cached.
Run from the repository root:

```powershell
$env:PHASE09_DB_PASSWORD=[guid]::NewGuid().ToString('N')
docker compose -f infra/docker/docker-compose.phase09-test.yml up -d --wait
$env:PGPASSWORD=$env:PHASE09_DB_PASSWORD
$env:DATABASE_URL='postgresql://phase09@127.0.0.1:55432/phase09'
$env:REDIS_URL='redis://127.0.0.1:56379/0'
$env:RUN_LIVE_DB_TESTS='1'
$env:RUN_LIVE_REDIS_TESTS='1'
$env:RUN_LIVE_PROVIDERS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest tests/db/test_phase09_live_integration.py tests/metering/test_phase09_live_redis.py -q --tb=short -p no:cacheprovider --basetemp hamza_local/pytest-phase09-disposable
docker compose -f infra/docker/docker-compose.phase09-test.yml down --volumes
Remove-Item Env:PHASE09_DB_PASSWORD,Env:PGPASSWORD,Env:DATABASE_URL,Env:REDIS_URL,Env:RUN_LIVE_DB_TESTS,Env:RUN_LIVE_REDIS_TESTS -ErrorAction SilentlyContinue
```

Expected result: `2 passed`. Return only that sanitized summary or the error;
do not paste the generated password or database URL.

## Human verification result

- Completed locally on 2026-10-23: `2 passed`.
- Fresh migrations, pgvector, unprivileged RLS, restart persistence, duplicate
  usage, migration idempotence, real Redis contention, double release, and
  expiry all passed.
- The first PostgreSQL run exposed a Windows event-loop mismatch. A test-local
  selector policy fixed it.
- The next run exposed an actual migration bug: the advisory lock opened an
  outer transaction, causing owned connections to roll back migrations at
  close. Owned migration connections now use autocommit while every migration
  remains wrapped in its own explicit transaction.
- Shared staging migration remains a separately approved deployment action.

## Next exact action

Proceed to Phase 10 planning. Do not migrate shared staging without a separate
approval naming that target.
