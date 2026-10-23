# Phase 09B Verification — Durable Repositories

**Date:** 2026-10-23

**Branch:** `wavia-fixv1`

**Base:** `6a0d6f0`

## Automated evidence

```text
focused repository/auth/agent/provider suite
100 passed, 1 skipped, 1 warning

ruff check <new Phase 09B modules and tests>
All checks passed

ruff check --select F,B <modified integration paths>
All checks passed

python -m compileall -q core control_plane worker_raw <Phase 09B tests>
exit 0
```

The skip is the explicitly disabled live database test. The warning is the
existing Starlette TestClient deprecation warning.

## Proven contracts

- protected environments reject process-local repository fallback;
- tenant and session operations use async transaction-local RLS context;
- database errors are propagated rather than silently switching to memory;
- session runtime plans survive repository round trips;
- agent versions are loaded as immutable tenant-scoped snapshots;
- API-key lookup accepts a hash only and updates use metadata in tenant scope;
- encrypted credentials persist with reference and rotation metadata;
- provider binding can resolve credentials asynchronously;
- audit writes and reads use tenant-scoped durable transactions.

## Next exact action

Create the 09B checkpoint commit and proceed to 09C Redis admission leases. Do
not push Phase 09 without a separate instruction.
