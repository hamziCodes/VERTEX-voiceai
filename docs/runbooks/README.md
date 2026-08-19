# UCVE Operational Runbooks

On-call playbooks (Phase 34). Severity aligned with Phase 25 `AlertRouter`.

## Severity

| Level | Description | Example alerts |
|---|---|---|
| SEV-3 | Degraded, workaround exists | `QUOTA_SOFT_WARN`, `LATENCY_SLO_BREACH` |
| SEV-2 | Customer-visible outage partial | `PROVIDER_UNAVAILABLE`, DLQ backlog |
| SEV-1 | Full outage or compliance incident | Quota hard block, HIPAA suspicion, worker fleet down |

## Runbooks

| Scenario | Runbook |
|---|---|
| Quota / cap exhaustion | [RUNBOOK_QUOTA_EXHAUSTION.md](RUNBOOK_QUOTA_EXHAUSTION.md) |
| Provider outage / failover | [RUNBOOK_PROVIDER_OUTAGE.md](RUNBOOK_PROVIDER_OUTAGE.md) |
| SIP trunk failover | [RUNBOOK_TRUNK_FAILOVER.md](RUNBOOK_TRUNK_FAILOVER.md) |
| DLQ backlog | [RUNBOOK_DLQ_BACKLOG.md](RUNBOOK_DLQ_BACKLOG.md) |
| Latency SLO breach | [RUNBOOK_LATENCY_SLO_BREACH.md](RUNBOOK_LATENCY_SLO_BREACH.md) |
| HIPAA / PHI incident | [RUNBOOK_HIPAA_INCIDENT.md](RUNBOOK_HIPAA_INCIDENT.md) |
| Worker OOM / memory | [RUNBOOK_WORKER_OOM.md](RUNBOOK_WORKER_OOM.md) |

## Alert channels (v1)

Email + tenant webhook (Phase 25). PagerDuty `[LATER]`.

## Incident template

Post-incident review: [../release/IncidentTemplate.md](../release/IncidentTemplate.md)
