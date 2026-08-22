-- Migration 014: Dead Letter Queue Schema with 30-Day Expiration TTL
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type VARCHAR(64) NOT NULL,
    payload_ref TEXT NOT NULL,
    error_code VARCHAR(64) NOT NULL,
    attempts INT NOT NULL DEFAULT 1,
    max_attempts INT NOT NULL DEFAULT 3,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '30 days')
);

CREATE INDEX IF NOT EXISTS idx_dlq_tenant_expiry ON dead_letter_queue(tenant_id, expires_at);
