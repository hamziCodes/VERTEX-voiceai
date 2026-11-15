# Runbook: deploys, drain and rollback

## Shutdown behaviour

| Service | On SIGTERM |
|---|---|
| worker-raw | Readiness → `draining` (503); new sessions refused with 1013; exits when the last local session ends or after `WAVIA_DRAIN_TIMEOUT_S` (default 120 s). A second signal exits immediately. |
| worker-jobs | Stops scheduling, lets in-flight items finish (`WAVIA_JOBS_DRAIN_S`, default 30 s). Interrupted items are safe: row leases expire and another runner retries them; singleton slots are re-claimable after their lease. |
| control plane, telephony gateway | Standard uvicorn graceful shutdown of in-flight HTTP requests. |

The orchestrator's stop grace period must exceed the drain timeout (compose: worker-raw 130 s, worker-jobs 40 s).

Verified by `python -m tests.scaling.drain_drill`: signalled mid-call → readiness 503 draining, new session refused 1013, live call finished, exit code 0.

## Rolling deploy order

1. **Migrations first, expand-only.** Migrations add tables/columns/constraints that the previous release ignores (Phase 14's 034 and 035 are additive). Never drop or rename in the same release that stops using something.
2. Control plane (mints plans the old workers can still load: plan snapshots carry `SESSION_PLAN_SCHEMA_VERSION`, and the realtime protocol accepts any `1.x` client).
3. Workers, one batch at a time, each draining before replacement.
4. Jobs runner.

Check after each step: `/health/ready` 200 on new instances, `WaviaHttp5xxRateHigh` quiet, `ucve_turn_latency_ms` unchanged.

## Rollback

Roll the application back to the previous image (migrations stay; they were expand-only). If a migration itself must be reverted, restore from backup (RUNBOOK_BACKUP_RESTORE) — there are no down-migrations.
