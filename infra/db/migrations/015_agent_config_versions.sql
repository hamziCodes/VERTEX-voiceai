-- Migration 015: Self-Serve Agent Builder Domain Model & Version Pinning
-- Supports draft autosave, immutable published versions, and session pinning.

CREATE TABLE IF NOT EXISTS agent_configs (
    agent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    current_version INT NOT NULL DEFAULT 1,
    draft_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_autosaved_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_config_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agent_configs(agent_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version INT NOT NULL,
    config_snapshot JSONB NOT NULL,
    published_by VARCHAR(255) DEFAULT 'system',
    published_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent_id, version)
);

CREATE TABLE IF NOT EXISTS session_config_pins (
    session_id UUID PRIMARY KEY,
    agent_id UUID NOT NULL REFERENCES agent_configs(agent_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    version_id UUID NOT NULL REFERENCES agent_config_versions(version_id) ON DELETE RESTRICT,
    version INT NOT NULL,
    pinned_config_snapshot JSONB NOT NULL,
    pinned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_configs_tenant ON agent_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_agent_versions_lookup ON agent_config_versions(agent_id, version);
CREATE INDEX IF NOT EXISTS idx_session_pins_tenant ON session_config_pins(tenant_id, session_id);

-- RLS Tenant Isolation Policies
ALTER TABLE agent_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_configs FORCE ROW LEVEL SECURITY;

CREATE POLICY agent_configs_tenant_isolation ON agent_configs
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE agent_config_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_config_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY agent_versions_tenant_isolation ON agent_config_versions
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE session_config_pins ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_config_pins FORCE ROW LEVEL SECURITY;

CREATE POLICY session_pins_tenant_isolation ON session_config_pins
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
