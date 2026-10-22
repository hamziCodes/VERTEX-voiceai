-- API-key identity and lifecycle metadata for management-plane authorization.
-- Raw API keys are never persisted.

ALTER TABLE api_keys
    ADD COLUMN IF NOT EXISTS subject_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS role VARCHAR(64) NOT NULL DEFAULT 'tenant_viewer',
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(255),
    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

UPDATE api_keys
SET subject_id = 'api-key:' || id::text
WHERE subject_id IS NULL;

ALTER TABLE api_keys
    ALTER COLUMN subject_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS api_keys_key_hash_unique
    ON api_keys (key_hash);

CREATE INDEX IF NOT EXISTS api_keys_tenant_active_idx
    ON api_keys (tenant_id, revoked_at, expires_at);
