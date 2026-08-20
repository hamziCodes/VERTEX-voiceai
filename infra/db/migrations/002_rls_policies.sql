-- UCVE Row-Level Security (RLS) Policies Migration
-- Migration: 002_rls_policies.sql
-- Description: Enforces tenant_id isolation via Postgres RLS session variable app.tenant_id.

-- Enable RLS on all tenant-owned tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_compliance_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_recordings ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE quota_state ENABLE ROW LEVEL SECURITY;

-- 1. Tenants RLS Policy
CREATE POLICY tenant_isolation_policy ON tenants
    FOR ALL
    USING (id::text = current_setting('app.tenant_id', true));

-- 2. Tenant Compliance Profile RLS Policy
CREATE POLICY compliance_profile_isolation_policy ON tenant_compliance_profile
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 3. Agents RLS Policy
CREATE POLICY agents_isolation_policy ON agents
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 4. Sessions RLS Policy
CREATE POLICY sessions_isolation_policy ON sessions
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 5. Session Transcripts RLS Policy
CREATE POLICY transcripts_isolation_policy ON session_transcripts
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 6. Session Recordings RLS Policy
CREATE POLICY recordings_isolation_policy ON session_recordings
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 7. Usage Events RLS Policy
CREATE POLICY usage_events_isolation_policy ON usage_events
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- 8. Quota State RLS Policy
CREATE POLICY quota_state_isolation_policy ON quota_state
    FOR ALL
    USING (tenant_id::text = current_setting('app.tenant_id', true));
