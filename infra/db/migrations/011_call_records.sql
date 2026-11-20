-- Migration 011: Post-Call Intelligence CallRecords Table
CREATE TABLE IF NOT EXISTS call_records (
    call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    session_id UUID NOT NULL,
    caller_id VARCHAR(20) DEFAULT NULL, -- E.164 caller phone number if telephony-origin
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    end_reason VARCHAR(64) NOT NULL DEFAULT 'user_hangup',
    transport_type VARCHAR(32) NOT NULL DEFAULT 'websocket',
    disposition VARCHAR(64) NOT NULL DEFAULT 'completed',
    turns_jsonb JSONB NOT NULL DEFAULT '[]'::jsonb,
    recording_s3_uri TEXT DEFAULT NULL,
    dual_channel BOOLEAN NOT NULL DEFAULT TRUE,
    compliance_tier VARCHAR(32) NOT NULL DEFAULT 'standard',
    memory_embed_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    transcript_raw_ref TEXT DEFAULT NULL,
    transcript_redacted_ref TEXT DEFAULT NULL,
    verification_issues_jsonb JSONB NOT NULL DEFAULT '[]'::jsonb,
    metrics_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_records_tenant_id ON call_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_call_records_session_id ON call_records(session_id);
CREATE INDEX IF NOT EXISTS idx_call_records_caller_id ON call_records(caller_id);

-- RLS Tenant Isolation Policies (FIX-026)
ALTER TABLE call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_records FORCE ROW LEVEL SECURITY;

CREATE POLICY call_records_tenant_isolation ON call_records
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
