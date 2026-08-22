-- Migration 012: Extraction Schemas, Webhook Targets & Human Review Queue Schema
CREATE TABLE IF NOT EXISTS extraction_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL DEFAULT 'default',
    fields_jsonb JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_fields INT NOT NULL DEFAULT 50,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS webhook_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret VARCHAR(255) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS human_review_queue (
    issue_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID NOT NULL REFERENCES call_records(call_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    field_path VARCHAR(128) NOT NULL,
    extracted_value TEXT DEFAULT NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_human_review_queue_tenant ON human_review_queue(tenant_id, status);

-- RLS Tenant Isolation Policies (FIX-026)
ALTER TABLE extraction_schemas ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_schemas FORCE ROW LEVEL SECURITY;
CREATE POLICY extraction_schemas_tenant_isolation ON extraction_schemas
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

ALTER TABLE webhook_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_targets FORCE ROW LEVEL SECURITY;
CREATE POLICY webhook_targets_tenant_isolation ON webhook_targets
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);

ALTER TABLE human_review_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_review_queue FORCE ROW LEVEL SECURITY;
CREATE POLICY human_review_queue_tenant_isolation ON human_review_queue
    FOR ALL USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
