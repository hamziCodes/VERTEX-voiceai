-- UCVE Retention & GDPR Erasure Migration
-- Migration: 005_retention_erasure.sql
-- Description: Adds dual transcript columns, purge_after timestamp, legal hold, and erasure_requests table.

ALTER TABLE session_transcripts
    ADD COLUMN IF NOT EXISTS transcript_raw_encrypted TEXT,
    ADD COLUMN IF NOT EXISTS transcript_redacted JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS purge_after TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS legal_hold BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS erasure_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(64) NOT NULL DEFAULT 'pending'
);

ALTER TABLE erasure_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY erasure_requests_isolation_policy ON erasure_requests
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));
