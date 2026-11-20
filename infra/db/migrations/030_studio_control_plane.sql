-- Studio external identity, workspace onboarding, entitlements, and draft revisions.

ALTER TABLE users
    ALTER COLUMN email DROP NOT NULL,
    ALTER COLUMN password_hash DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS is_platform_admin BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE external_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    issuer VARCHAR(1024) NOT NULL,
    subject VARCHAR(512) NOT NULL,
    email_snapshot VARCHAR(320),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (issuer, subject)
);

CREATE INDEX idx_external_identities_user
    ON external_identities (user_id);

CREATE TABLE workspace_invitations (
    invitation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    role VARCHAR(64) NOT NULL CHECK (
        role IN (
            'tenant_admin',
            'tenant_editor',
            'tenant_viewer',
            'compliance_admin'
        )
    ),
    token_hash CHAR(64) NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    invited_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    accepted_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (accepted_at IS NULL AND accepted_by IS NULL)
        OR (accepted_at IS NOT NULL AND accepted_by IS NOT NULL)
    )
);

CREATE INDEX idx_workspace_invitations_tenant_created
    ON workspace_invitations (tenant_id, created_at DESC);
CREATE INDEX idx_workspace_invitations_expiry
    ON workspace_invitations (expires_at)
    WHERE accepted_at IS NULL;

CREATE TABLE tenant_onboarding_profiles (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    business_name VARCHAR(255) NOT NULL DEFAULT '',
    use_case VARCHAR(64) NOT NULL DEFAULT '',
    languages TEXT[] NOT NULL DEFAULT ARRAY['en']::TEXT[],
    operating_region VARCHAR(128) NOT NULL DEFAULT '',
    timezone VARCHAR(128) NOT NULL DEFAULT 'UTC',
    escalation_email VARCHAR(320),
    completed_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (cardinality(languages) > 0),
    CHECK (jsonb_typeof(completed_steps) = 'array')
);

CREATE TABLE tenant_entitlements (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    max_agents INTEGER NOT NULL DEFAULT 1 CHECK (max_agents BETWEEN 1 AND 10000),
    max_concurrent_sessions INTEGER NOT NULL DEFAULT 1
        CHECK (max_concurrent_sessions BETWEEN 1 AND 10000),
    max_knowledge_bytes BIGINT NOT NULL DEFAULT 10485760
        CHECK (max_knowledge_bytes >= 0),
    api_keys_allowed INTEGER NOT NULL DEFAULT 2
        CHECK (api_keys_allowed BETWEEN 0 AND 10000),
    telephony_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    advanced_providers_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    byok_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    allowed_retention_days INTEGER[] NOT NULL DEFAULT ARRAY[7, 30]::INTEGER[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        cardinality(allowed_retention_days) = 0
        OR (
            0 < ALL (allowed_retention_days)
            AND 3650 >= ALL (allowed_retention_days)
        )
    )
);

ALTER TABLE agent_configs
    ADD COLUMN IF NOT EXISTS draft_revision BIGINT NOT NULL DEFAULT 1
        CHECK (draft_revision > 0);

ALTER TABLE workspace_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_invitations FORCE ROW LEVEL SECURITY;
CREATE POLICY workspace_invitations_tenant_isolation
    ON workspace_invitations FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

ALTER TABLE tenant_onboarding_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_onboarding_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_onboarding_profiles_tenant_isolation
    ON tenant_onboarding_profiles FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

ALTER TABLE tenant_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_entitlements FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_entitlements_tenant_isolation
    ON tenant_entitlements FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );

GRANT SELECT, INSERT, UPDATE, DELETE ON
    workspace_invitations,
    tenant_onboarding_profiles,
    tenant_entitlements
TO ucve_app;

REVOKE ALL ON external_identities FROM ucve_app;
