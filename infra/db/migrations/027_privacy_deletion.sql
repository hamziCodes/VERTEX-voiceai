-- Restart-safe privacy deletion, legal holds, and legacy webhook quarantine.

ALTER TABLE call_records
    ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE call_records
SET purge_after = COALESCE(ended_at, started_at) + make_interval(
    days => CASE
        WHEN COALESCE(policy_snapshot ->> 'transcript_retention_days', '') ~ '^\d+$'
            THEN LEAST((policy_snapshot ->> 'transcript_retention_days')::INTEGER, 30)
        ELSE 30
    END
)
WHERE finalized_at IS NOT NULL AND purge_after IS NULL;

CREATE INDEX IF NOT EXISTS idx_call_records_retention_due
    ON call_records (purge_after)
    WHERE finalized_at IS NOT NULL AND purge_after IS NOT NULL AND legal_hold = FALSE;

CREATE TABLE IF NOT EXISTS privacy_deletion_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_kind VARCHAR(32) NOT NULL,
    request_key VARCHAR(255) NOT NULL,
    call_id UUID,
    object_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    completed_object_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
    database_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    state VARCHAR(32) NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 20),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(128),
    lease_expires_at TIMESTAMPTZ,
    last_error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, request_key),
    CONSTRAINT privacy_jobs_kind_check CHECK (
        job_kind IN ('retention', 'tenant_erasure')
    ),
    CONSTRAINT privacy_jobs_call_check CHECK (
        (job_kind = 'retention' AND call_id IS NOT NULL)
        OR (job_kind = 'tenant_erasure' AND call_id IS NULL)
    ),
    CONSTRAINT privacy_jobs_state_check CHECK (
        state IN ('queued', 'running', 'retry_wait', 'succeeded', 'dead_letter')
    ),
    CONSTRAINT privacy_jobs_lease_check CHECK (
        (state = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR (state <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_privacy_deletion_jobs_claim
    ON privacy_deletion_jobs (state, available_at, created_at);

ALTER TABLE privacy_deletion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE privacy_deletion_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY privacy_deletion_jobs_tenant_isolation
    ON privacy_deletion_jobs FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON privacy_deletion_jobs TO ucve_app;

ALTER TABLE webhook_targets
    ALTER COLUMN secret DROP NOT NULL,
    ALTER COLUMN enabled SET DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS credential_ref VARCHAR(255),
    ADD COLUMN IF NOT EXISTS migration_state VARCHAR(32) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS migrated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS migration_error_code VARCHAR(64),
    ADD COLUMN IF NOT EXISTS migration_attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS migration_max_attempts INTEGER NOT NULL DEFAULT 5,
    ADD COLUMN IF NOT EXISTS migration_available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS migration_lease_owner VARCHAR(128),
    ADD COLUMN IF NOT EXISTS migration_lease_expires_at TIMESTAMPTZ;

UPDATE webhook_targets SET enabled = FALSE WHERE enabled = TRUE;

ALTER TABLE webhook_targets
    DROP CONSTRAINT IF EXISTS webhook_targets_legacy_disabled_check,
    ADD CONSTRAINT webhook_targets_legacy_disabled_check CHECK (enabled = FALSE),
    DROP CONSTRAINT IF EXISTS webhook_targets_migration_state_check,
    ADD CONSTRAINT webhook_targets_migration_state_check CHECK (
        migration_state IN ('pending', 'running', 'migrated', 'failed')
    ),
    DROP CONSTRAINT IF EXISTS webhook_targets_migration_attempt_check,
    ADD CONSTRAINT webhook_targets_migration_attempt_check CHECK (
        migration_attempt_count >= 0
        AND migration_max_attempts BETWEEN 1 AND 20
        AND migration_attempt_count <= migration_max_attempts
    ),
    DROP CONSTRAINT IF EXISTS webhook_targets_migration_lease_check,
    ADD CONSTRAINT webhook_targets_migration_lease_check CHECK (
        (
            migration_state = 'running'
            AND migration_lease_owner IS NOT NULL
            AND migration_lease_expires_at IS NOT NULL
        )
        OR (
            migration_state <> 'running'
            AND migration_lease_owner IS NULL
            AND migration_lease_expires_at IS NULL
        )
    ),
    DROP CONSTRAINT IF EXISTS webhook_targets_migration_evidence_check,
    ADD CONSTRAINT webhook_targets_migration_evidence_check CHECK (
        migration_state <> 'migrated'
        OR (
            secret IS NULL
            AND credential_ref IS NOT NULL
            AND migrated_at IS NOT NULL
            AND migration_error_code IS NULL
        )
    );

DROP POLICY IF EXISTS webhook_targets_tenant_isolation ON webhook_targets;
CREATE POLICY webhook_targets_tenant_isolation
    ON webhook_targets FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON webhook_targets TO ucve_app;
