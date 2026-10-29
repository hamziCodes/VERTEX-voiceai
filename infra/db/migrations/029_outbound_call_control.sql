-- Controlled one-call outbound policy, durable idempotency, and trunk identity.

ALTER TABLE sip_trunks
    ADD COLUMN IF NOT EXISTS connection_id VARCHAR(255) NOT NULL DEFAULT '';

CREATE TABLE telephony_outbound_policies (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_destinations TEXT[] NOT NULL DEFAULT '{}',
    calling_timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    window_start TIME NOT NULL DEFAULT '09:00',
    window_end TIME NOT NULL DEFAULT '17:00',
    max_concurrent_calls INTEGER NOT NULL CHECK (max_concurrent_calls > 0),
    max_calls_per_minute INTEGER NOT NULL CHECK (max_calls_per_minute > 0),
    daily_spend_cap_cents INTEGER NOT NULL CHECK (daily_spend_cap_cents > 0),
    reserved_spend_cents_per_call INTEGER NOT NULL
        CHECK (reserved_spend_cents_per_call > 0),
    max_call_duration_seconds INTEGER NOT NULL
        CHECK (max_call_duration_seconds BETWEEN 1 AND 14400),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (cardinality(allowed_destinations) > 0),
    CHECK (reserved_spend_cents_per_call <= daily_spend_cap_cents)
);

CREATE TABLE telephony_outbound_requests (
    request_id UUID PRIMARY KEY,
    command_id UUID NOT NULL UNIQUE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    agent_id UUID NOT NULL,
    destination VARCHAR(32) NOT NULL,
    purpose VARCHAR(120) NOT NULL,
    consent_reference VARCHAR(255) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    request_fingerprint CHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL CHECK (
        status IN ('reserved', 'submitting', 'submitted', 'ambiguous', 'failed', 'ended')
    ),
    requested_at TIMESTAMPTZ NOT NULL,
    reserved_spend_cents INTEGER NOT NULL CHECK (reserved_spend_cents > 0),
    call_control_id VARCHAR(512),
    call_leg_id VARCHAR(128),
    call_session_id VARCHAR(128),
    failure_code VARCHAR(128),
    published_version_id UUID NOT NULL,
    published_version INTEGER NOT NULL CHECK (published_version > 0),
    did_id UUID NOT NULL,
    from_number VARCHAR(32) NOT NULL,
    trunk_id UUID NOT NULL,
    provider VARCHAR(32) NOT NULL,
    credential_ref VARCHAR(255) NOT NULL,
    connection_id VARCHAR(255) NOT NULL,
    media_stream_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, request_id),
    FOREIGN KEY (tenant_id, agent_id)
        REFERENCES agents(tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, did_id)
        REFERENCES telephony_dids(tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, agent_id, published_version_id, published_version)
        REFERENCES agent_config_versions(tenant_id, agent_id, version_id, version)
        ON DELETE RESTRICT,
    CHECK (destination ~ '^\+[1-9][0-9]{7,14}$'),
    CHECK (from_number ~ '^\+[1-9][0-9]{7,14}$')
);

CREATE INDEX idx_outbound_requests_tenant_status
    ON telephony_outbound_requests (tenant_id, status, requested_at DESC);
CREATE INDEX idx_outbound_requests_tenant_rate
    ON telephony_outbound_requests (tenant_id, requested_at DESC);

ALTER TABLE telephony_outbound_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_outbound_policies FORCE ROW LEVEL SECURITY;
CREATE POLICY telephony_outbound_policies_tenant_isolation
    ON telephony_outbound_policies FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE telephony_outbound_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_outbound_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY telephony_outbound_requests_tenant_isolation
    ON telephony_outbound_requests FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    telephony_outbound_policies, telephony_outbound_requests TO ucve_app;
