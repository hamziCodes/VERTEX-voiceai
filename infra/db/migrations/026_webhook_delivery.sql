-- Reviewed webhook destinations and durable replay-safe deliveries.

CREATE TABLE IF NOT EXISTS post_call_webhook_targets (
    target_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    credential_ref VARCHAR(255) NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'pending',
    reviewed_by VARCHAR(255),
    reviewed_at TIMESTAMPTZ,
    approved_addresses JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, target_id),
    CONSTRAINT post_call_webhook_targets_state_check CHECK (
        state IN ('pending', 'active', 'disabled')
    ),
    CONSTRAINT post_call_webhook_targets_review_check CHECK (
        state <> 'active'
        OR (
            reviewed_by IS NOT NULL
            AND reviewed_at IS NOT NULL
            AND jsonb_array_length(approved_addresses) > 0
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_post_call_reviews_tenant_review
    ON post_call_review_requests (tenant_id, review_id);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    delivery_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    target_id UUID NOT NULL,
    call_id UUID NOT NULL,
    result_id UUID NOT NULL,
    review_id UUID NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    idempotency_key CHAR(64) NOT NULL,
    payload_jsonb JSONB NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner VARCHAR(128),
    lease_expires_at TIMESTAMPTZ,
    last_status_code INTEGER,
    last_error_code VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, delivery_id),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, target_id, call_id, event_type),
    FOREIGN KEY (tenant_id, target_id)
        REFERENCES post_call_webhook_targets(tenant_id, target_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES call_records(tenant_id, call_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, result_id)
        REFERENCES post_call_intelligence_results(tenant_id, result_id)
        ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, review_id)
        REFERENCES post_call_review_requests(tenant_id, review_id)
        ON DELETE RESTRICT,
    CONSTRAINT webhook_deliveries_state_check CHECK (
        state IN ('queued', 'running', 'retry_wait', 'succeeded', 'dead_letter')
    ),
    CONSTRAINT webhook_deliveries_lease_check CHECK (
        (state = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR
        (state <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)
    ),
    CONSTRAINT webhook_deliveries_status_check CHECK (
        last_status_code IS NULL OR last_status_code BETWEEN 100 AND 599
    )
);

CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_claim
    ON webhook_deliveries (state, available_at, created_at);

CREATE TABLE IF NOT EXISTS webhook_delivery_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    delivery_id UUID NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number >= 1),
    outcome VARCHAR(32) NOT NULL,
    status_code INTEGER,
    error_code VARCHAR(64),
    duration_ms INTEGER NOT NULL CHECK (duration_ms >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, delivery_id, attempt_number),
    FOREIGN KEY (tenant_id, delivery_id)
        REFERENCES webhook_deliveries(tenant_id, delivery_id) ON DELETE CASCADE,
    CONSTRAINT webhook_attempts_outcome_check CHECK (
        outcome IN ('succeeded', 'retryable_failure', 'terminal_failure')
    ),
    CONSTRAINT webhook_attempts_status_check CHECK (
        status_code IS NULL OR status_code BETWEEN 100 AND 599
    )
);

ALTER TABLE post_call_webhook_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE post_call_webhook_targets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS post_call_webhook_targets_tenant_isolation
    ON post_call_webhook_targets;
CREATE POLICY post_call_webhook_targets_tenant_isolation
    ON post_call_webhook_targets FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE webhook_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_deliveries FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS webhook_deliveries_tenant_isolation ON webhook_deliveries;
CREATE POLICY webhook_deliveries_tenant_isolation
    ON webhook_deliveries FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE webhook_delivery_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_delivery_attempts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS webhook_attempts_tenant_isolation
    ON webhook_delivery_attempts;
CREATE POLICY webhook_attempts_tenant_isolation
    ON webhook_delivery_attempts FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    post_call_webhook_targets,
    webhook_deliveries,
    webhook_delivery_attempts
TO ucve_app;
