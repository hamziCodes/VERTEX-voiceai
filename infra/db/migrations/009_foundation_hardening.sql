-- UCVE Foundation Hardening schema fixes (H3)
-- Migration: 009_foundation_hardening.sql

-- Force RLS on tenant-scoped tables
ALTER TABLE IF EXISTS tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS agents FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS session_transcripts FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS session_recordings FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS tenant_credentials FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS usage_events FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS quota_state FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS audit_log FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS mint_rejections FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS erasure_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS api_keys FORCE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS memberships FORCE ROW LEVEL SECURITY;

-- Users are platform-global (email login); disable tenant RLS if present
ALTER TABLE IF EXISTS users DISABLE ROW LEVEL SECURITY;

-- Audit log must not CASCADE-wipe on tenant delete — RESTRICT (or soft-delete tenants)
ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_tenant_id_fkey;
ALTER TABLE audit_log
    ADD CONSTRAINT audit_log_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE mint_rejections DROP CONSTRAINT IF EXISTS mint_rejections_tenant_id_fkey;
ALTER TABLE mint_rejections
    ADD CONSTRAINT mint_rejections_tenant_id_fkey
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE SET NULL;

-- Retention purge index (skip legal hold)
CREATE INDEX IF NOT EXISTS idx_sessions_purge_after_active
    ON sessions (purge_after)
    WHERE legal_hold = false AND purge_after IS NOT NULL;

-- Dual-column transcript alignment (idempotent with 005)
ALTER TABLE session_transcripts
    ADD COLUMN IF NOT EXISTS transcript_raw_encrypted TEXT,
    ADD COLUMN IF NOT EXISTS transcript_redacted JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Optional generated view preserving legacy `turns` consumers
CREATE OR REPLACE VIEW session_transcript_turns AS
SELECT
    id,
    session_id,
    tenant_id,
    COALESCE(transcript_redacted, turns, '[]'::jsonb) AS turns,
    metadata,
    created_at
FROM session_transcripts;

-- Soft-delete support for tenants (prefer over hard delete that would block on audit RESTRICT)
ALTER TABLE tenants
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
