-- Durable session runtime-plan state required by worker admission and refresh.

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS agent_config_version INT,
    ADD COLUMN IF NOT EXISTS runtime_plan_hash CHAR(64),
    ADD COLUMN IF NOT EXISTS runtime_plan_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS session_language VARCHAR(32),
    ADD COLUMN IF NOT EXISTS session_voice_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_sessions_runtime_plan
    ON sessions (tenant_id, id, runtime_plan_hash);

ALTER TABLE tenant_credentials
    ADD COLUMN IF NOT EXISTS credential_ref VARCHAR(255) NOT NULL DEFAULT 'default',
    ADD COLUMN IF NOT EXISTS rotation_version INT NOT NULL DEFAULT 1;

ALTER TABLE tenant_credentials
    DROP CONSTRAINT IF EXISTS uq_tenant_provider_cred;

ALTER TABLE tenant_credentials
    ADD CONSTRAINT uq_tenant_provider_cred_ref
    UNIQUE (tenant_id, provider_id, credential_type, credential_ref);
