# Wavia operational runbooks

On-call playbooks. Every command, endpoint, metric and alert named here exists in the code as of Phase 14; if you find one that does not, the runbook is wrong — fix it.

## Signals

| Signal | Where |
|---|---|
| Liveness | `GET /health/live` on every service (process only; never checks dependencies) |
| Readiness | `GET /health/ready` — per-check status, `draining` during shutdown. Ports: control plane 8080, worker-raw 8081, worker-managed 8082 (always not-ready; roadmap), telephony gateway 8083, jobs runner 8084 |
| Metrics | `GET /metrics` with `Authorization: Bearer $UCVE_METRICS_BEARER` on every service (Prometheus text) |
| Traces | OTLP/HTTP to `OTEL_EXPORTER_OTLP_ENDPOINT` when `OTEL_EXPORTER_ENABLED=true` |
| Logs | JSON on stdout with `service`, `request_id`, `trace_id`, `session_id`, `turn_id`; PII, credentials and conversation content are redacted |
| Job schedule | `GET :8084/jobs` (same bearer) — each job's last outcome, items, failures, or why it is disabled |
| Platform view | Studio `/admin/operations`; API `GET /v1/platform/operations`, `GET /v1/platform/alerts` (platform admin) |

Local collector for verifying export: `infra/docker/docker-compose.observability.yml`.

## Alerts

Two layers, both real:

1. **Durable application alerts** (`operational_alerts`, raised by the services): `QUOTA_SOFT_CAP`, `QUOTA_EXHAUSTED`, `CAPACITY_EXHAUSTED`, `PROVIDER_CHAIN_EXHAUSTED`, `JOB_DEAD_LETTER`, `JOB_RUN_FAILED`. De-duplicated by key, visible in `/admin/operations`, tenant-scoped ones visible to the tenant at `GET /v1/alerts/{tenant_id}`. Delivered as HMAC-signed webhooks to `WAVIA_ALERT_WEBHOOK_URL` (header `X-Wavia-Alert-Signature: t=<unix>,v1=<hex sha256 of "<t>.<body>">`); without a URL they are recorded `not_configured`. There is no email channel.
2. **Metric alerts** (`infra/observability/prometheus-alerts.yml`, validated with `promtool check rules`): latency SLO p95/p50, failover rate, readiness, scrape down, event-loop lag, worker at capacity, 5xx rate, dead letters, failing jobs, silent jobs runner.

## Severity

| Level | Meaning | Examples |
|---|---|---|
| SEV-3 | Degraded, workaround exists | `QUOTA_SOFT_CAP`, `WaviaTurnLatencyP95AboveSLO`, `WaviaEventLoopLagHigh` |
| SEV-2 | Partial customer-visible outage | `PROVIDER_CHAIN_EXHAUSTED` for one category, `JOB_DEAD_LETTER`, `WaviaServiceNotReady` |
| SEV-1 | Full outage | every worker not ready, all provider categories down, control plane down |

## Runbooks

| Scenario | Runbook |
|---|---|
| Quota / plan limits | [RUNBOOK_QUOTA_EXHAUSTION.md](RUNBOOK_QUOTA_EXHAUSTION.md) |
| Provider outage / failover | [RUNBOOK_PROVIDER_OUTAGE.md](RUNBOOK_PROVIDER_OUTAGE.md) |
| SIP trunk failover | [RUNBOOK_TRUNK_FAILOVER.md](RUNBOOK_TRUNK_FAILOVER.md) |
| Dead letters / failing jobs | [RUNBOOK_DLQ_BACKLOG.md](RUNBOOK_DLQ_BACKLOG.md) |
| Latency SLO breach | [RUNBOOK_LATENCY_SLO_BREACH.md](RUNBOOK_LATENCY_SLO_BREACH.md) |
| Worker capacity / memory | [RUNBOOK_WORKER_OOM.md](RUNBOOK_WORKER_OOM.md) |
| Deploys, drain and rollback | [RUNBOOK_DEPLOY_AND_DRAIN.md](RUNBOOK_DEPLOY_AND_DRAIN.md) |
| Backup and restore | [RUNBOOK_BACKUP_RESTORE.md](RUNBOOK_BACKUP_RESTORE.md) |
| Privacy incident | [RUNBOOK_HIPAA_INCIDENT.md](RUNBOOK_HIPAA_INCIDENT.md) — compliance scope pending decision H14; treat as a general personal-data incident runbook until then |

## Incident template

Post-incident review: [../release/IncidentTemplate.md](../release/IncidentTemplate.md)
