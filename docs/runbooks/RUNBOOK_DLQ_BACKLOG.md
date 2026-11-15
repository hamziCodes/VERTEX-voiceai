# Runbook: dead letters and failing jobs

The jobs runner (`python -m worker_jobs.main`, port 8084) drains four durable queues. Each row carries its own lease, retries with backoff and ends in a terminal state when retries are exhausted:

| Job family | Table | Terminal state |
|---|---|---|
| `post_call_intelligence` | `post_call_jobs` | `dead_letter` |
| `webhook_delivery` | `webhook_deliveries` | `dead_letter` |
| `privacy_deletion` | `privacy_deletion_jobs` | `dead_letter` |
| `knowledge_ingestion` | `knowledge_ingestion_jobs` | `failed` |

## Signals

- Alert `JOB_DEAD_LETTER` (key `job_dead_letter:<family>`, facts: count) — raised by the `queue_observer` job every 60 s, resolved automatically when the count returns to 0.
- Alert `JOB_RUN_FAILED` (key `job_run_failed:<job>`) after three consecutive failed runs; resolved on the next good run.
- Metrics: `ucve_job_queue_depth{job,state}`, `ucve_jobs_total{job,outcome}`; Prometheus rules `WaviaJobsDeadLettered`, `WaviaJobRunsFailing`, `WaviaJobsRunnerSilent`.
- `GET :8084/jobs` (bearer) shows each job's last outcome, error type and whether it is disabled and why.

## Immediate actions

1. Open `/admin/operations` → **Operational alerts** to see which family and how many.
2. `GET :8084/jobs` — if the job is `disabled`, the reason says what is missing (for example `no structured extraction/summary provider configured`, `UCVE_EMBEDDING_MODEL_PATH not configured`). Disabled jobs never claim success.
3. Inspect rows by error code only — never transcripts:

   ```sql
   SELECT state, last_error_code, count(*) FROM webhook_deliveries GROUP BY 1, 2;
   SELECT state, last_error_code, count(*) FROM privacy_deletion_jobs GROUP BY 1, 2;
   SELECT state, last_error_code, count(*) FROM post_call_jobs GROUP BY 1, 2;
   ```
4. Webhooks: confirm the tenant endpoint is reachable and its signing secret is still valid (`post_call_webhook_targets` row state and `credential_ref`; there is no Studio or API surface for webhook targets yet — tracked as a product gap).
5. Privacy deletion: `legal_hold` failures are expected while a hold is active; `object_delete_failed` means the object store refused a delete — check `UCVE_RECORDING_S3_*` credentials and bucket policy.

## Replay

There is no automatic replay of dead-lettered rows (that would defeat the dead letter). After fixing the cause, requeue explicitly and record it in the incident:

```sql
UPDATE webhook_deliveries SET state = 'queued', available_at = NOW()
WHERE state = 'dead_letter' AND delivery_id = '<id>';
```

## Escalation

SEV-2 if any family has dead letters for more than 1 hour or `WaviaJobsRunnerSilent` fires. SEV-1 if privacy deletion is stuck past its retention deadline.
