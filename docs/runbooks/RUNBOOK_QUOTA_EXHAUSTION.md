# Runbook: Quota Exhaustion

Phase 14 usage metering thresholds. Ports habiba cap exhaustion pattern.

## Symptoms

- `QUOTA_SOFT_WARN` alert at **80%** of tenant quota
- `QUOTA_EXCEEDED` at **100%** — mint returns 503
- Dashboard usage graph flatlines at cap

## Immediate actions

1. Confirm tenant_id from alert (no PHI in ticket).
2. Check Redis quota counter vs Postgres usage ledger (Phase 14).
3. **80%:** notify tenant admin via email webhook; no hard block yet.
4. **100%:** new sessions rejected; active sessions continue until disconnect.

## Mitigation

| Action | When |
|---|---|
| Temporary quota bump | Contracted overage approved |
| Ask tenant to reduce concurrency | Self-serve |
| Scale workers | Cluster capacity, not quota — see RUNBOOK_WORKER_OOM |

## Escalation

SEV-3 at 80%; SEV-2 at 100% for paid tier > 15 min.

## Prevention

- Set tenant alert contacts in control-plane (Phase 25)
- Review Phase 31 admission limits vs quota

## Related

- [../developer/TROUBLESHOOTING.md](../developer/TROUBLESHOOTING.md) — `QUOTA_EXCEEDED`
