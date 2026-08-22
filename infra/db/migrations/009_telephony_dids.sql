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

-- RLS Tenant Isolation Policies (FIX-026)
ALTER TABLE telephony_dids ENABLE ROW LEVEL SECURITY;
ALTER TABLE telephony_dids FORCE ROW LEVEL SECURITY;

CREATE POLICY telephony_dids_tenant_isolation ON telephony_dids
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
