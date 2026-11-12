-- Phase 13K: audited, read-only, expiring support sessions.
--
-- A Wavia staff member opens a session from the internal tenant summary with a
-- reason, a bounded read scope and an expiry of at most 60 minutes. Only that
-- staff member may read through it, only while it is active and only for the
-- granted scopes. There is deliberately no write scope.

CREATE TABLE IF NOT EXISTS platform_support_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    reference TEXT,
    scopes TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    ended_by UUID REFERENCES users(id) ON DELETE RESTRICT,
    end_reason TEXT,
    CONSTRAINT platform_support_sessions_reason_check CHECK (
        char_length(btrim(reason)) BETWEEN 8 AND 500
    ),
    CONSTRAINT platform_support_sessions_reference_check CHECK (
        reference IS NULL OR char_length(btrim(reference)) BETWEEN 1 AND 64
    ),
    CONSTRAINT platform_support_sessions_scopes_check CHECK (
        cardinality(scopes) BETWEEN 1 AND 2
        AND scopes <@ ARRAY['configuration', 'readiness']::TEXT[]
    ),
    CONSTRAINT platform_support_sessions_expiry_check CHECK (
        expires_at > created_at
        AND expires_at <= created_at + INTERVAL '60 minutes'
    ),
    CONSTRAINT platform_support_sessions_end_check CHECK (
        (ended_at IS NULL AND ended_by IS NULL AND end_reason IS NULL)
        OR (
            ended_at IS NOT NULL
            AND ended_by IS NOT NULL
            AND (end_reason IS NULL OR char_length(btrim(end_reason)) BETWEEN 8 AND 500)
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_platform_support_sessions_open
    ON platform_support_sessions (actor_user_id, tenant_id)
    WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_platform_support_sessions_created
    ON platform_support_sessions (created_at DESC, session_id);

-- Platform audit gains support activity. Adding nullable columns and widening a
-- CHECK constraint does not update existing rows, so the append-only trigger is
-- untouched.
ALTER TABLE platform_audit_events
    ADD COLUMN IF NOT EXISTS support_session_id UUID,
    ADD COLUMN IF NOT EXISTS scope TEXT;

ALTER TABLE platform_audit_events
    DROP CONSTRAINT IF EXISTS platform_audit_events_action_check,
    ADD CONSTRAINT platform_audit_events_action_check CHECK (
        action IN (
            'platform_staff.migrated',
            'platform_staff.granted',
            'platform_staff.role_changed',
            'platform_staff.revoked',
            'platform_tenant.viewed',
            'platform_support.session_started',
            'platform_support.session_ended',
            'platform_support.data_viewed'
        )
    );

ALTER TABLE platform_audit_events
    DROP CONSTRAINT IF EXISTS platform_audit_events_scope_check,
    ADD CONSTRAINT platform_audit_events_scope_check CHECK (
        scope IS NULL OR scope IN ('configuration', 'readiness')
    );

ALTER TABLE platform_support_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_support_sessions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON platform_support_sessions FROM ucve_app;
