# Runbook: DLQ Backlog

Phase 25 dead-letter queue — 30-day retention.

## Symptoms

- DLQ depth metric rising (Phase 07)
- `DISPATCH_FAILED` / `EXTRACTION_FAILED` alerts
- CRM webhooks not receiving post-call payloads

## Immediate actions

1. Query DLQ by `error_code` — admin RBAC + audit log (Phase 12).
2. Inspect **refs only** — no raw transcript in operator view.
3. Check tenant webhook endpoint reachability and HMAC secret (fail-closed Phase 21).

## Retry

- `worker-jobs/dlq_retry_sweeper.py` runs every 5 min, max 3 attempts
- Manual replay via admin API for idempotent jobs

## Purge

- Entries expire after **30 days** (Phase 11 alignment)
- Legal hold exception — do not purge held job_ids

## Escalation

SEV-2 if backlog > 1000 jobs or oldest job > 24 h without retry success.

## Prevention

- Tenant webhook SLA monitoring
- Schema validation before publish (Phase 21)
