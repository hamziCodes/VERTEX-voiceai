# Support and operations handoff — 0.1.0-rc1

For whoever operates Wavia after release. Everything here exists in the
repository and was exercised offline; production specifics (hosts, pager,
dashboards) are filled in when the AWS me-central-1 deployment is approved.

## Services and health

| Service | Port | Liveness | Readiness checks |
|---|---|---|---|
| control-plane | 8080 | `/health/live` | database, Redis, runtime profile, identity (OIDC), providers (advisory) |
| worker-raw | 8081 | `/health/live` | database, Redis, runtime profile, session capacity; VAD model and providers advisory |
| worker-jobs | 8084 | `/health/live` | database, scheduler; `/jobs` (bearer) lists every job and why any is disabled |
| telephony-gateway | 8083 | `/health/live` | database, Telnyx webhook verifier, runtime profile |

`/metrics` on every service (bearer `UCVE_METRICS_BEARER`) exposes the
`ucve_*` series. Readiness 503 with `"status":"draining"` during shutdown is
expected.

## Alerts and where they lead

| Prometheus rule (`infra/observability/prometheus-alerts.yml`) / alert code | Runbook |
|---|---|
| `WaviaTurnLatencyP95AboveSLO`, `WaviaTurnLatencyP50AboveTarget`, `LATENCY_SLO_BREACH` | `docs/runbooks/RUNBOOK_LATENCY_SLO_BREACH.md` |
| `WaviaProviderFailoverRateHigh`, `PROVIDER_CHAIN_EXHAUSTED` | `RUNBOOK_PROVIDER_OUTAGE.md` |
| `QUOTA_SOFT_CAP` (80%), `QUOTA_EXHAUSTED` (100%) | `RUNBOOK_QUOTA_EXHAUSTION.md` |
| `WaviaWorkerAtCapacity`, `CAPACITY_EXHAUSTED`, `WaviaEventLoopLagHigh` | `RUNBOOK_WORKER_OOM.md`, `docs/scaling/AUTOSCALING.md` |
| `WaviaJobsDeadLettered`, `WaviaJobRunsFailing`, `WaviaJobsRunnerSilent`, `JOB_DEAD_LETTER`, `JOB_RUN_FAILED` | `RUNBOOK_DLQ_BACKLOG.md` |
| `WaviaServiceNotReady`, `WaviaMetricsScrapeDown`, `WaviaHttp5xxRateHigh` | `RUNBOOK_DEPLOY_AND_DRAIN.md` |
| Carrier trunk problems | `RUNBOOK_TRUNK_FAILOVER.md` |
| Database loss, restore | `RUNBOOK_BACKUP_RESTORE.md` |

Operational alerts are also listed for staff at `GET /v1/platform/alerts`
and resolved with `POST /v1/platform/alerts/{id}/resolve`
(`platform_alerts:manage`); tenants see their own at `GET /v1/alerts/{tenant_id}`.
Webhook delivery of alerts is signed (`X-Wavia-Alert-Signature`).

`RUNBOOK_HIPAA_INCIDENT.md` is an incident procedure only; Wavia makes no
HIPAA, GDPR or SOC claims at launch (H14).

## Customer support

- Staff roles and audited, read-only support sessions:
  `/v1/platform/tenants/{id}/support-sessions` (time-boxed, every read
  audited in `platform_audit_events`).
- Privacy requests: legal hold `POST /v1/conversations/{id}/legal-hold`,
  deletion `POST /v1/conversations/{id}/deletion`, workspace erasure
  `POST /v1/workspace/erasure`, status `GET /v1/privacy-jobs/{id}`; the
  append-only trail is `privacy_deletion_events`.
- SDK connection failures surface `SessionRejectedError` with the WebSocket
  close code and reason:
  - 4401 invalid or expired session: mint again.
  - 4403 forbidden: provider-mode mismatch or a disallowed override.
  - 1013 retryable server condition, with the reason saying which: `worker
    draining`, `worker at capacity`, `cluster at capacity`, `session store
    unavailable` (Redis or database), `session admission unavailable`. Mint
    a new session and retry after a short backoff.
  - 1011 provider setup failed: check the tenant's provider credentials.
- HTTP 503 with `"code": "DATABASE_UNAVAILABLE"` and `Retry-After` means the
  database is unreachable; `/health/ready` reports the same. A Redis outage
  answers 503 "temporarily unavailable" on mint and refresh.

## Release, rollback, drills

- Rollback: `docs/release/ROLLBACK.md` (image rollback, forward-only
  migrations).
- Drills: `bash scripts/release/drills.sh`, `scripts/ops/drill_backup_restore.sh`,
  `scripts/ops/run_privacy_proof.sh`, `python -m tests.scaling.drain_drill`.
- Qualification stack: `bash scripts/release/container_stack.sh up|down`.

## Open items handed over

See "Known limitations" in `RELEASE_NOTES_0.1.0-rc1.md`; most urgent:
post-call intelligence provider, webhook-target management, live
certification (H15).
