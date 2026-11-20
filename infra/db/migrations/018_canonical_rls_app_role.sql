-- Canonical tenant RLS boundary and unprivileged application role.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ucve_app') THEN
        CREATE ROLE ucve_app NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO ucve_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ucve_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ucve_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ucve_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO ucve_app;

ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation_policy ON tenants;
CREATE POLICY tenant_isolation_policy ON tenants FOR ALL TO ucve_app
    USING (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenant_compliance_profile FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS compliance_profile_isolation_policy ON tenant_compliance_profile;
CREATE POLICY compliance_profile_isolation_policy ON tenant_compliance_profile
    FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE agents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agents_isolation_policy ON agents;
CREATE POLICY agents_isolation_policy ON agents FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS sessions_isolation_policy ON sessions;
CREATE POLICY sessions_isolation_policy ON sessions FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE session_transcripts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS transcripts_isolation_policy ON session_transcripts;
CREATE POLICY transcripts_isolation_policy ON session_transcripts FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE session_recordings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS recordings_isolation_policy ON session_recordings;
CREATE POLICY recordings_isolation_policy ON session_recordings FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE tenant_credentials FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_credentials_isolation_policy ON tenant_credentials;
CREATE POLICY tenant_credentials_isolation_policy ON tenant_credentials FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE usage_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS usage_events_isolation_policy ON usage_events;
CREATE POLICY usage_events_isolation_policy ON usage_events FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE quota_state FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS quota_state_isolation_policy ON quota_state;
CREATE POLICY quota_state_isolation_policy ON quota_state FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_log_tenant_isolation ON audit_log;
CREATE POLICY audit_log_tenant_isolation ON audit_log FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE mint_rejections FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS mint_rejections_tenant_isolation ON mint_rejections;
CREATE POLICY mint_rejections_tenant_isolation ON mint_rejections FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE erasure_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erasure_requests_isolation_policy ON erasure_requests;
CREATE POLICY erasure_requests_isolation_policy ON erasure_requests FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS memberships_isolation ON memberships;
CREATE POLICY memberships_isolation ON memberships FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS api_keys_isolation ON api_keys;
CREATE POLICY api_keys_isolation ON api_keys FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE telephony_dids FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS telephony_dids_tenant_isolation ON telephony_dids;
CREATE POLICY telephony_dids_tenant_isolation ON telephony_dids FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE call_records FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS call_records_tenant_isolation ON call_records;
CREATE POLICY call_records_tenant_isolation ON call_records FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE extraction_schemas FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS extraction_schemas_tenant_isolation ON extraction_schemas;
CREATE POLICY extraction_schemas_tenant_isolation ON extraction_schemas FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE webhook_targets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS webhook_targets_tenant_isolation ON webhook_targets;
CREATE POLICY webhook_targets_tenant_isolation ON webhook_targets FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE human_review_queue FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS human_review_queue_tenant_isolation ON human_review_queue;
CREATE POLICY human_review_queue_tenant_isolation ON human_review_queue FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE knowledge_chunks FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS knowledge_chunks_tenant_isolation ON knowledge_chunks;
CREATE POLICY knowledge_chunks_tenant_isolation ON knowledge_chunks FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE dead_letter_queue FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dead_letter_queue_tenant_isolation ON dead_letter_queue;
CREATE POLICY dead_letter_queue_tenant_isolation ON dead_letter_queue FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE agent_configs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_configs_tenant_isolation ON agent_configs;
CREATE POLICY agent_configs_tenant_isolation ON agent_configs FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE agent_config_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_versions_tenant_isolation ON agent_config_versions;
CREATE POLICY agent_versions_tenant_isolation ON agent_config_versions FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE session_config_pins FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS session_pins_tenant_isolation ON session_config_pins;
CREATE POLICY session_pins_tenant_isolation ON session_config_pins FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
