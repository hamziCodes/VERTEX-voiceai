-- Tenant-owned MCP server registry. Credentials remain references only.

CREATE TABLE IF NOT EXISTS mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    transport VARCHAR(32) NOT NULL DEFAULT 'streamable_http',
    endpoint TEXT NOT NULL,
    credential_ref VARCHAR(255),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    side_effecting_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    idempotency_supported_tools JSONB NOT NULL DEFAULT '[]'::jsonb,
    availability VARCHAR(32) NOT NULL DEFAULT 'unknown',
    last_error_code VARCHAR(64),
    last_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT mcp_servers_transport_check CHECK (
        transport IN ('streamable_http', 'stdio', 'sse')
    ),
    CONSTRAINT mcp_servers_availability_check CHECK (
        availability IN ('unknown', 'available', 'unavailable', 'degraded')
    ),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, name)
);

CREATE TABLE IF NOT EXISTS mcp_server_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    server_id UUID NOT NULL,
    tool_name VARCHAR(255) NOT NULL,
    description VARCHAR(1000) NOT NULL DEFAULT '',
    input_schema JSONB NOT NULL,
    side_effecting BOOLEAN NOT NULL DEFAULT FALSE,
    idempotency_supported BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, server_id, tool_name),
    UNIQUE (tenant_id, tool_name),
    FOREIGN KEY (tenant_id, server_id)
        REFERENCES mcp_servers(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_tenant_enabled
    ON mcp_servers (tenant_id, enabled, created_at);
CREATE INDEX IF NOT EXISTS idx_mcp_server_tools_owner
    ON mcp_server_tools (tenant_id, server_id, tool_name);

ALTER TABLE mcp_servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_servers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mcp_servers_tenant_isolation ON mcp_servers;
CREATE POLICY mcp_servers_tenant_isolation ON mcp_servers FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE mcp_server_tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_server_tools FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mcp_server_tools_tenant_isolation ON mcp_server_tools;
CREATE POLICY mcp_server_tools_tenant_isolation ON mcp_server_tools FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_servers, mcp_server_tools TO ucve_app;
