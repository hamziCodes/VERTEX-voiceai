# Phase 09A — Database, Migrations, pgvector, and RLS

**Status:** VERIFIED — AWAITING CHECKPOINT COMMIT

## Decision

Use async Psycopg 3 plus `psycopg_pool`. All tenant database work runs inside
one transaction that sets `app.tenant_id` transaction-locally before queries.
Production repositories must receive this database boundary instead of opening
sync connections themselves.

## Implemented

- Added an async connection-pool boundary with tenant and platform transaction
  context managers.
- Protected environments fail closed when `DATABASE_URL` is absent.
- Replaced duplicate migration number 009 with migration 017 and retained a
  legacy filename alias for safe upgrades.
- Added unique migration-number validation, SHA-256 checksums, advisory locking,
  and schema plus bookkeeping in the same transaction.
- Standardized migrations on `app.tenant_id`.
- Switched disposable Compose PostgreSQL to the pgvector PostgreSQL 16 image.
- Added migration 018 to rebuild tenant policies for the non-login `ucve_app`
  role with both `USING` and `WITH CHECK` boundaries.

## Verification

```text
pytest tests/db/test_phase09_database.py tests/hardening/test_h3_persistence.py -q
13 passed, 1 skipped
```

The skipped test requires an explicitly enabled disposable PostgreSQL target.
No shared database or migration target was contacted.
