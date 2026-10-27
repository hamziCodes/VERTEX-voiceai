# Phase 11D-2 Verification Evidence

**Date:** 2026-10-27

**Branch:** `wavia-fixv1`

**Implementation commit:** `a854b9e`

**Result:** PASS

## Delivered behavior

- Added bounded, region-aware local and S3-compatible recording object storage with strict reference validation and idempotent deletion.
- Added durable PostgreSQL retention and tenant-erasure jobs with stable request keys, worker leases, retry/dead-letter state, per-object checkpoints, and a database-deletion checkpoint.
- Legal hold blocks deletion before object access and is rechecked under the database deletion transaction.
- Call finalization now stores its transcript purge deadline from the immutable policy snapshot. A bounded scheduler query creates due retention jobs.
- Tenant erasure deletes operational records, preserves immutable audit rows, and scrubs/soft-deletes the tenant tombstone.
- Migration 027 quarantines the unused legacy raw-secret webhook table and adds the privacy job schema under tenant RLS.
- The legacy migration leases one row, writes the signing secret into the encrypted tenant vault, creates a disabled pending replacement target, and only then clears the raw value. Failure retains the source value for a safe retry without logging it.

## Failure-first evidence

The initial focused test run failed collection because the object-store, privacy-job, deletion-worker, and legacy-migration modules did not exist. The missing contracts were implemented after that red baseline. The focused suite then passed before the PostgreSQL adapters and disposable integration proof were added.

## Automated verification

### Focused offline suite

```powershell
py -3.12 -m pytest tests/post_call/test_recording_storage.py tests/compliance/test_phase11_erasure.py tests/post_call/test_legacy_webhook_migration.py tests/db/test_phase11d_migration.py tests/db/test_phase11d_live_integration.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11d2-focused-final
```

Result: **11 passed, 1 skipped**. The skipped test is explicitly gated to disposable PostgreSQL.

### Disposable PostgreSQL proof

A fresh loopback-only `pgvector/pgvector:pg16` database and Redis container used a generated password and temporary volumes. The test applied all migrations, simulated a process restart after an object checkpoint, completed retention deletion, migrated a generated legacy secret into encrypted storage, performed tenant erasure, preserved the immutable audit row, verified cross-tenant RLS, and reapplied migrations idempotently.

```powershell
$env:RUN_LIVE_DB_TESTS='1'
py -3.12 -m pytest tests/db/test_phase11d_live_integration.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11d2-live
```

Result: **1 passed**. Test containers, network, and disposable volumes were removed.

### Full forced-offline suite

```powershell
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:RUN_LIVE_PROVIDERS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase11d2-full
```

Result: **865 passed, 11 skipped, 2 warnings** in 35.22 seconds. Both warnings are the existing intentionally short HMAC fixtures in `tests/hardening/test_h1_auth_crypto.py`.

### Static and integrity gates

- Ruff formatting and changed-file lint: **passed**.
- Scoped mypy: **6 source files passed**.
- Python compilation: **passed**.
- `git diff --check`: **passed**.
- Plan integrity: **`OK: 36 phases, tests, and trackers verified.`**
- The Windows test runner created a literal `%SystemDrive%` cache directory. Its four OS cache files were inspected and moved intact to gitignored `hamza_local/pytest-os-cache-phase11d2`; nothing was deleted.

## Boundaries

- No environment file or raw-key file was read.
- No live provider, webhook destination, telephony carrier, cloud bucket, shared database, deployment, paid traffic, or production deletion was used.
- Migration 027 was applied only to a disposable local database. Production migration remains a deployment operation requiring its own backup, review, and change window.
- Legacy targets remain pending after migration and require the existing human review and destination approval before activation.

## Next exact action

Begin Phase 12A with failure-first tests for the authenticated Telnyx webhook contract: signature verification over exact request bytes, replay rejection, timestamp bounds, tenant/trunk resolution, and safe idempotent call admission. Do not place a live call or contact Telnyx during 12A.
