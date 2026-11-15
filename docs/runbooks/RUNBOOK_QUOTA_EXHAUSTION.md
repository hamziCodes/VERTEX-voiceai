# Runbook: quota and plan limits

Usage and concurrency limits are enforced at session mint (`POST /v1/session/mint`). Monthly usage is derived from the usage ledger for the current calendar month; no reset job exists or is needed.

## Signals

| Event | Response to the caller | Alert |
|---|---|---|
| Soft threshold passed | Session allowed; header `X-UCVE-Quota-Warning: soft_cap` | `QUOTA_SOFT_CAP` (warning, one per tenant per month) |
| Plan limit reached | `429` | `QUOTA_EXHAUSTED` (error, one per tenant per month) |
| Fleet capacity reached (not a plan limit) | `503` "Worker capacity limit reached" | `CAPACITY_EXHAUSTED` (platform) |

Tenants see their own quota alerts at `GET /v1/alerts/{tenant_id}`; staff see all in `/admin/operations`.

## Immediate actions

1. Distinguish plan limit (429, tenant alert) from fleet capacity (503, platform alert). Capacity is an operations problem — see RUNBOOK_WORKER_OOM.
2. For a plan limit, check the tenant's entitlements in `/admin` (tenant summary). Active sessions continue; only new sessions are refused.
3. Any limit change is a commercial decision; record who approved it.

## Escalation

SEV-3 at the soft threshold; SEV-2 if a paying tenant is blocked for more than 15 minutes without an approved decision.
