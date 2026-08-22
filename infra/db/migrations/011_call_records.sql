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
    metrics_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_call_records_tenant_id ON call_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_call_records_session_id ON call_records(session_id);
CREATE INDEX IF NOT EXISTS idx_call_records_caller_id ON call_records(caller_id);
