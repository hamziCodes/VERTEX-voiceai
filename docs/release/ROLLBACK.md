# Rollback plan

Wavia rolls back by **image**, never by reversing migrations. This works
because migrations are forward-only and additive: the previous release's
code runs against the newer schema (proved by the Phase 15 rollback drill,
`bash scripts/release/drills.sh upgrade rollback`).

## Before every release

1. Record the current image digests of every service (control plane,
   worker-raw, worker-jobs, telephony gateway) — these are the rollback target.
2. Check the release's migrations are additive: no `DROP TABLE`, no dropped
   or renamed columns, no narrowed constraints that existing rows or the
   previous code would violate. If a migration is not additive, the release
   needs a two-step (expand, then contract in a later release) instead.
3. Take a database backup (managed snapshot/PITR in production; the logical
   path is drilled by `scripts/ops/drill_backup_restore.sh`).

## Rolling back

1. **Stop the bleeding.** Redeploy the previous image digests for the
   affected services. Workers drain on SIGTERM (`WAVIA_DRAIN_TIMEOUT_S`,
   default 120 s): live calls finish, new sessions are refused with 1013 and
   reconnect to a ready worker. See `docs/runbooks/RUNBOOK_DEPLOY_AND_DRAIN.md`.
2. **Do not run down-migrations.** The newer schema stays; the previous code
   ignores the tables and states it does not know.
3. **Verify.** `/health/ready` is 200 on every service; mint one session and
   complete one turn (`sdk/python/examples/quickstart.py` with a tenant API
   key); watch `ucve_http_requests_total{status_class="5xx"}` and the
   operational alerts list for 15 minutes.
4. **Record** the incident with `IncidentTemplate.md` and plan a forward fix.

## What a rollback does not change

- **In-flight sessions** keep the agent configuration pinned at mint until
  they end; new sessions use the latest published version.
- **Data written by the newer release** stays. Rows in states the previous
  code does not know (for example privacy jobs in `held`, added by migration
  036) are left alone by the previous code and resume when the newer release
  returns.
- **SDK clients** keep working as long as the server still satisfies the
  SDK's `min_server_version` and protocol range (`COMPATIBILITY.md`).

## When not to roll back

- The newer release fixed a security issue: roll forward with a fix instead.
- A migration in the newer release was not additive (step 2 above was
  skipped): restore from backup only with an incident commander's decision,
  because it loses data written since the backup.
