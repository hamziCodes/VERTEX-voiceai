-- Phase 14: durable claims for singleton scheduled jobs.
--
-- Queue drainers (post-call intelligence, webhook delivery, knowledge
-- embedding, privacy deletion) already lease individual rows with
-- FOR UPDATE SKIP LOCKED. Periodic singleton work (retention enqueue, queue
-- depth observation) needs "exactly one runner per time slot" across replicas:
-- a runner claims (job_name, slot_start) with an insert that only one replica
-- can win, holds a lease while it runs and records the outcome. A crashed
-- runner's expired lease can be taken over for the same slot.

CREATE TABLE IF NOT EXISTS scheduled_job_runs (
    job_name TEXT NOT NULL,
    slot_start TIMESTAMPTZ NOT NULL,
    runner_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_expires_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    items_processed INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    attempts INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (job_name, slot_start),
    CONSTRAINT scheduled_job_runs_status_check CHECK (
        status IN ('running', 'succeeded', 'failed')
    ),
    CONSTRAINT scheduled_job_runs_name_check CHECK (
        job_name ~ '^[a-z][a-z0-9_]{2,63}$'
    ),
    CONSTRAINT scheduled_job_runs_error_check CHECK (
        error_code IS NULL OR char_length(error_code) <= 64
    ),
    CONSTRAINT scheduled_job_runs_finish_check CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_scheduled_job_runs_recent
    ON scheduled_job_runs (job_name, slot_start DESC);

ALTER TABLE scheduled_job_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_job_runs FORCE ROW LEVEL SECURITY;
REVOKE ALL ON scheduled_job_runs FROM ucve_app;
