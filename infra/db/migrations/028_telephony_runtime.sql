-- Durable Telnyx call identity, lifecycle events, command idempotency, and RLS.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_agents_tenant_id'
    ) THEN
        ALTER TABLE agents ADD CONSTRAINT uq_agents_tenant_id UNIQUE (tenant_id, id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_telephony_dids_tenant_id'
    ) THEN
        ALTER TABLE telephony_dids ADD CONSTRAINT uq_telephony_dids_tenant_id
            UNIQUE (tenant_id, id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_agent_versions_runtime_pin'
    ) THEN
        ALTER TABLE agent_config_versions
            ADD CONSTRAINT uq_agent_versions_runtime_pin
            UNIQUE (tenant_id, agent_id, version_id, version);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'telephony_dids_tenant_agent_fk'
    ) THEN
        ALTER TABLE telephony_dids
            ADD CONSTRAINT telephony_dids_tenant_agent_fk
            FOREIGN KEY (tenant_id, agent_id)
            REFERENCES agents(tenant_id, id) ON DELETE RESTRICT NOT VALID;
    END IF;
END
$$;

ALTER TABLE telephony_dids
    DROP CONSTRAINT IF EXISTS telephony_dids_status_check;
ALTER TABLE telephony_dids
    ADD CONSTRAINT telephony_dids_status_check
    CHECK (status IN ('active', 'inactive', 'suspended')) NOT VALID;
ALTER TABLE telephony_dids
    DROP CONSTRAINT IF EXISTS telephony_dids_e164_check;
ALTER TABLE telephony_dids
    ADD CONSTRAINT telephony_dids_e164_check
    CHECK (did_number ~ '^\+[1-9][0-9]{7,14}$') NOT VALID;

CREATE TABLE telephony_calls (
    call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    internal_session_id UUID NOT NULL UNIQUE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    agent_id UUID NOT NULL,
    did_id UUID NOT NULL,
    did_number VARCHAR(32) NOT NULL,
    published_version_id UUID NOT NULL,
    published_version INTEGER NOT NULL CHECK (published_version > 0),
    carrier VARCHAR(32) NOT NULL,
    call_control_id VARCHAR(512) NOT NULL,
    call_leg_id VARCHAR(128) NOT NULL,
    carrier_session_id VARCHAR(128) NOT NULL,
    direction VARCHAR(16) NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    state VARCHAR(32) NOT NULL CHECK (
        state IN ('received', 'admitted', 'answered', 'media_active', 'ending', 'ended', 'failed')
    ),
    state_changed_at TIMESTAMPTZ NOT NULL,
    disconnect_reason VARCHAR(255),
    received_at TIMESTAMPTZ NOT NULL,
    admitted_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (carrier, call_control_id),
    UNIQUE (tenant_id, call_id),
    FOREIGN KEY (tenant_id, agent_id)
        REFERENCES agents(tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, did_id)
        REFERENCES telephony_dids(tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, agent_id, published_version_id, published_version)
        REFERENCES agent_config_versions(tenant_id, agent_id, version_id, version)
        ON DELETE RESTRICT
);

CREATE INDEX idx_telephony_calls_tenant_state
    ON telephony_calls (tenant_id, state, updated_at DESC);
CREATE INDEX idx_telephony_calls_carrier_session
    ON telephony_calls (carrier, carrier_session_id);

CREATE TABLE telephony_events (
    carrier_event_id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    call_id UUID NOT NULL,
    carrier VARCHAR(32) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    state_applied BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES telephony_calls(tenant_id, call_id) ON DELETE CASCADE
);

CREATE INDEX idx_telephony_events_call_time
    ON telephony_events (tenant_id, call_id, occurred_at, carrier_event_id);

CREATE TABLE telephony_commands (
    command_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    call_id UUID NOT NULL,
    command_name VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'reserved'
        CHECK (status IN ('reserved', 'executing', 'succeeded', 'failed', 'cancelled')),
    carrier_command_id VARCHAR(255),
    failure_code VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, idempotency_key),
    FOREIGN KEY (tenant_id, call_id)
        REFERENCES telephony_calls(tenant_id, call_id) ON DELETE CASCADE
);

CREATE INDEX idx_telephony_commands_call_status
    ON telephony_commands (tenant_id, call_id, status, created_at);

ALTER TABLE telephony_dids ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_dids FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS telephony_dids_tenant_isolation ON telephony_dids;
CREATE POLICY telephony_dids_tenant_isolation ON telephony_dids FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE sip_trunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE sip_trunks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sip_trunks_tenant_isolation ON sip_trunks;
CREATE POLICY sip_trunks_tenant_isolation ON sip_trunks FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE telephony_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_calls FORCE ROW LEVEL SECURITY;
CREATE POLICY telephony_calls_tenant_isolation ON telephony_calls FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE telephony_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_events FORCE ROW LEVEL SECURITY;
CREATE POLICY telephony_events_tenant_isolation ON telephony_events FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE telephony_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_commands FORCE ROW LEVEL SECURITY;
CREATE POLICY telephony_commands_tenant_isolation ON telephony_commands FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    telephony_calls, telephony_events, telephony_commands TO ucve_app;
