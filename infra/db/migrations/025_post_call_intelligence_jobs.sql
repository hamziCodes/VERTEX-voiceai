-- Durable post-call intelligence outbox, results, and human-review decisions.

ALTER TABLE call_records
    ADD COLUMN IF NOT EXISTS intelligence_config_snapshot JSONB NOT NULL
        DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS uq_call_records_tenant_call
    ON call_records (tenant_id, call_id);

CREATE TABLE IF NOT EXISTS post_call_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    call_id UUID NOT NULL,
    job_type VARCHAR(32) NOT NULL DEFAULT 'intelligence',
    state VARCHAR(32) NOT NULL DEFAULT 'queued',
    payload_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(128),
    lease_expires_at TIMESTAMPTZ,
    last_error_code VARCHAR(64),
    last_error_message VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, call_id, job_type),
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES call_records(tenant_id, call_id) ON DELETE CASCADE,
    CONSTRAINT post_call_jobs_type_check CHECK (job_type = 'intelligence'),
    CONSTRAINT post_call_jobs_state_check CHECK (
        state IN ('queued', 'running', 'retry_wait', 'succeeded', 'dead_letter')
    ),
    CONSTRAINT post_call_jobs_lease_check CHECK (
        (state = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR
        (state <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_post_call_jobs_claim
    ON post_call_jobs (state, available_at, created_at);

CREATE TABLE IF NOT EXISTS post_call_intelligence_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    call_id UUID NOT NULL,
    extraction_jsonb JSONB,
    summary_jsonb JSONB,
    verification_issue_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, call_id),
    UNIQUE (tenant_id, result_id),
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES call_records(tenant_id, call_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS post_call_review_requests (
    review_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    call_id UUID NOT NULL,
    result_id UUID NOT NULL,
    reasons_jsonb JSONB NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'pending',
    decided_by VARCHAR(255),
    decision_note VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decided_at TIMESTAMPTZ,
    UNIQUE (tenant_id, result_id),
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES call_records(tenant_id, call_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, result_id)
        REFERENCES post_call_intelligence_results(tenant_id, result_id)
        ON DELETE CASCADE,
    CONSTRAINT post_call_review_state_check CHECK (
        state IN ('pending', 'approved', 'rejected')
    ),
    CONSTRAINT post_call_review_decision_check CHECK (
        (
            state = 'pending'
            AND decided_by IS NULL
            AND decided_at IS NULL
        )
        OR
        (
            state IN ('approved', 'rejected')
            AND decided_by IS NOT NULL
            AND decided_at IS NOT NULL
        )
    )
);

INSERT INTO post_call_jobs (
    tenant_id, call_id, payload_jsonb, available_at, created_at, updated_at
)
SELECT
    tenant_id,
    call_id,
    intelligence_config_snapshot,
    COALESCE(ended_at, NOW()),
    COALESCE(ended_at, NOW()),
    NOW()
FROM call_records
WHERE ended_at IS NOT NULL
ON CONFLICT (tenant_id, call_id, job_type) DO NOTHING;

ALTER TABLE post_call_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_call_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_call_jobs_tenant_isolation ON post_call_jobs;
CREATE POLICY post_call_jobs_tenant_isolation ON post_call_jobs FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE post_call_intelligence_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_call_intelligence_results FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_call_results_tenant_isolation
    ON post_call_intelligence_results;
CREATE POLICY post_call_results_tenant_isolation
    ON post_call_intelligence_results FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE post_call_review_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_call_review_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_call_reviews_tenant_isolation
    ON post_call_review_requests;
CREATE POLICY post_call_reviews_tenant_isolation
    ON post_call_review_requests FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    post_call_jobs,
    post_call_intelligence_results,
    post_call_review_requests
TO ucve_app;
