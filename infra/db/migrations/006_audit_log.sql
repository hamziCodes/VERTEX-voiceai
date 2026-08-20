-- UCVE Compliance Audit Trail & Immutability Migration
-- Migration: 006_audit_log.sql
-- Description: Creates audit_log, mint_rejections, and immutability triggers blocking UPDATE/DELETE.

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    actor_id VARCHAR(255) NOT NULL,
    actor_type VARCHAR(64) NOT NULL DEFAULT 'system',
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(128) NOT NULL,
    resource_id VARCHAR(255) NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip VARCHAR(64),
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_at ON audit_log(tenant_id, created_at DESC);

-- Mint rejections tracking table (Habiba pattern)
CREATE TABLE IF NOT EXISTS mint_rejections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    ip VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE mint_rejections ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_log_tenant_isolation ON audit_log
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

CREATE POLICY mint_rejections_tenant_isolation ON mint_rejections
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- Immutability Trigger: Reject UPDATE or DELETE on audit_log
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log records are immutable and cannot be updated or deleted.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER audit_log_no_update_delete
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
