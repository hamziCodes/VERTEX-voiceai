-- Phase 14: legal-hold aware deletion jobs and an append-only deletion record.
--
-- 1. A retention or erasure job that meets a legal hold is parked in state
--    'held' (not retried into a dead letter). Releasing the hold requeues it.
-- 2. privacy_deletion_events records every lifecycle step of every deletion
--    job: requested, held, released, objects deleted, database deleted,
--    completed, failed, dead-lettered. It holds identifiers, codes and counts
--    only (no content), has no foreign key to tenants so it survives tenant
--    erasure as the proof that erasure happened, and cannot be updated or
--    deleted.

ALTER TABLE privacy_deletion_jobs
    DROP CONSTRAINT IF EXISTS privacy_jobs_state_check,
    ADD CONSTRAINT privacy_jobs_state_check CHECK (
        state IN ('queued', 'running', 'retry_wait', 'succeeded', 'dead_letter', 'held')
    );

ALTER TABLE privacy_deletion_jobs
    DROP CONSTRAINT IF EXISTS privacy_jobs_kind_check,
    ADD CONSTRAINT privacy_jobs_kind_check CHECK (
        job_kind IN ('retention', 'tenant_erasure')
    );

CREATE TABLE IF NOT EXISTS privacy_deletion_events (
    event_id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL,
    tenant_id UUID NOT NULL,
    job_kind VARCHAR(32) NOT NULL,
    call_id UUID,
    event VARCHAR(32) NOT NULL,
    error_code VARCHAR(64),
    actor VARCHAR(128) NOT NULL DEFAULT 'system',
    counts JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT privacy_deletion_events_event_check CHECK (
        event IN (
            'requested', 'held', 'released', 'objects_deleted',
            'database_deleted', 'completed', 'failed', 'dead_lettered'
        )
    ),
    CONSTRAINT privacy_deletion_events_kind_check CHECK (
        job_kind IN ('retention', 'tenant_erasure')
    )
);

CREATE INDEX IF NOT EXISTS idx_privacy_deletion_events_job
    ON privacy_deletion_events (job_id, event_id);
CREATE INDEX IF NOT EXISTS idx_privacy_deletion_events_tenant
    ON privacy_deletion_events (tenant_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_privacy_event_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'privacy_deletion_events is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER privacy_deletion_events_no_update_delete
    BEFORE UPDATE OR DELETE ON privacy_deletion_events
    FOR EACH ROW EXECUTE FUNCTION prevent_privacy_event_modification();

ALTER TABLE privacy_deletion_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy_deletion_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON privacy_deletion_events FROM ucve_app;
GRANT SELECT ON privacy_deletion_events TO ucve_app;
DROP POLICY IF EXISTS privacy_deletion_events_tenant_read ON privacy_deletion_events;
CREATE POLICY privacy_deletion_events_tenant_read
    ON privacy_deletion_events FOR SELECT TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
