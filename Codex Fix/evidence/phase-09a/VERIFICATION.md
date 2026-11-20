# Phase 09A Verification — Database and Migration Foundation

**Date:** 2026-10-23

**Branch:** `wavia-fixv1`

**Base:** `51e8c87f11e813cc7280b8f0ce2c4b94ce34227e`

## Automated evidence

```text
pytest tests/db/test_phase09_database.py tests/hardening/test_h3_persistence.py -q
13 passed, 1 skipped

ruff check core/db/async_pg.py infra/db/migrate.py \
  tests/db/test_phase09_database.py tests/hardening/test_h3_persistence.py
All checks passed

python -m compileall -q core/db infra/db tests/db
exit 0
```

The skipped test is the explicitly gated disposable PostgreSQL integration
test. No shared database, Redis, provider, telephony, or paid service was used.

## Proven contracts

- tenant context is set inside a transaction with a bound parameter;
- staging/production cannot silently run without a database URL;
- migration versions are unique and checksums detect source drift;
- fresh installs use the pgvector PostgreSQL image;
- all source migrations use `app.tenant_id`;
- the forward RLS migration creates an unprivileged role and rebuilds policies.

## Next exact action

Create the 09A checkpoint commit, then implement 09B durable repositories. Do
not push Phase 09 without a separate instruction.
