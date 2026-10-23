-- Narrow RLS-safe API-key authentication lookup. Raw keys are never persisted.

CREATE OR REPLACE FUNCTION authenticate_api_key(p_key_hash VARCHAR(64))
RETURNS TABLE (
    key_id UUID,
    subject_id VARCHAR(255),
    tenant_id UUID,
    name VARCHAR(128),
    scopes JSONB,
    role VARCHAR(64),
    created_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT id, api_keys.subject_id, api_keys.tenant_id, api_keys.name,
           api_keys.scopes, api_keys.role, api_keys.created_at,
           api_keys.expires_at, api_keys.revoked_at, api_keys.last_used_at
    FROM api_keys
    WHERE key_hash = p_key_hash
    LIMIT 1
$$;

REVOKE ALL ON FUNCTION authenticate_api_key(VARCHAR) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION authenticate_api_key(VARCHAR) TO ucve_app;
