-- Migration 010: Multi-Trunk SIP Configurations Schema
CREATE TABLE IF NOT EXISTS sip_trunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL DEFAULT 'telnyx',
    credentials_ref VARCHAR(255) NOT NULL, -- Key Vault reference, e.g. 'vault://tenant_id/telnyx'
    webhook_public_key TEXT DEFAULT '',
    priority INT NOT NULL DEFAULT 1, -- 1 = highest priority
    role VARCHAR(32) NOT NULL DEFAULT 'primary', -- primary / secondary / sandbox
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    region VARCHAR(32) NOT NULL DEFAULT 'us',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sip_trunks_tenant_priority ON sip_trunks(tenant_id, priority);
