-- UCVE Tenant Credential Vaulting Migration
-- Migration: 003_tenant_credentials.sql
-- Description: Creates tenant_credentials table for encrypted provider API keys and credential metadata.

CREATE TABLE IF NOT EXISTS tenant_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider_id VARCHAR(128) NOT NULL,
    credential_type VARCHAR(64) NOT NULL DEFAULT 'api_key',
    encrypted_blob TEXT NOT NULL,
    key_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tenant_provider_cred UNIQUE (tenant_id, provider_id, credential_type)
);

CREATE INDEX IF NOT EXISTS idx_tenant_credentials_lookup ON tenant_credentials(tenant_id, provider_id);

-- Enable RLS
ALTER TABLE tenant_credentials ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_credentials_isolation_policy ON tenant_credentials
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));
