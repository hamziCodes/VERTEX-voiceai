-- Migration 009: Telephony DIDs Inventory Schema
CREATE TABLE IF NOT EXISTS telephony_dids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    did_number VARCHAR(32) NOT NULL UNIQUE, -- E.164 format, e.g. '+18005550199'
    carrier VARCHAR(32) NOT NULL DEFAULT 'telnyx',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telephony_dids_did_number ON telephony_dids(did_number);
CREATE INDEX IF NOT EXISTS idx_telephony_dids_tenant_id ON telephony_dids(tenant_id);
