-- Phase 13J: durable Wavia platform staff roles and platform audit.
--
-- Replaces authorization by users.is_platform_admin (a cross-tenant wildcard)
-- with explicit platform memberships. The boolean column is kept for
-- compatibility but is no longer read for authorization.
--
-- Platform tables are never granted to ucve_app. They are reached only through
-- the platform database role used by platform_transaction (the same role that
-- already resolves identities across tenants).

CREATE TABLE IF NOT EXISTS platform_memberships (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    granted_by UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    revoke_reason TEXT,
    CONSTRAINT platform_memberships_role_check CHECK (
        role IN ('platform_admin', 'platform_support')
    ),
    CONSTRAINT platform_memberships_reason_check CHECK (
        char_length(btrim(reason)) BETWEEN 8 AND 500
    ),
    CONSTRAINT platform_memberships_revocation_check CHECK (
        (revoked_at IS NULL AND revoke_reason IS NULL)
        OR (
            revoked_at IS NOT NULL
            AND char_length(btrim(revoke_reason)) BETWEEN 8 AND 500
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_platform_memberships_active_role
    ON platform_memberships (role, user_id)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS platform_audit_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- Plain identifiers (no foreign keys): audit rows are append-only and
    -- must survive later changes to the users or tenants they mention.
    actor_user_id UUID,
    action TEXT NOT NULL,
    target_user_id UUID,
    target_tenant_id UUID,
    previous_role TEXT,
    new_role TEXT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT platform_audit_events_action_check CHECK (
        action IN (
            'platform_staff.migrated',
            'platform_staff.granted',
            'platform_staff.role_changed',
            'platform_staff.revoked',
            'platform_tenant.viewed'
        )
    ),
    CONSTRAINT platform_audit_events_role_check CHECK (
        (previous_role IS NULL OR previous_role IN ('platform_admin', 'platform_support'))
        AND (new_role IS NULL OR new_role IN ('platform_admin', 'platform_support'))
    )
);

CREATE INDEX IF NOT EXISTS idx_platform_audit_events_created
    ON platform_audit_events (created_at DESC, event_id);

CREATE OR REPLACE FUNCTION prevent_platform_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Platform audit events are immutable and cannot be updated or deleted.';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER platform_audit_events_no_update_delete
BEFORE UPDATE OR DELETE ON platform_audit_events
FOR EACH ROW EXECUTE FUNCTION prevent_platform_audit_modification();

-- One-time backfill of the legacy flag. Idempotent: users that already hold a
-- platform membership row are skipped, so no duplicate audit event is written.
WITH migrated AS (
    INSERT INTO platform_memberships (user_id, role, granted_by, reason)
    SELECT u.id, 'platform_admin', NULL, 'Migrated from users.is_platform_admin'
    FROM users u
    WHERE u.is_platform_admin = TRUE
    ON CONFLICT (user_id) DO NOTHING
    RETURNING user_id
)
INSERT INTO platform_audit_events (action, target_user_id, new_role, reason)
SELECT 'platform_staff.migrated', user_id, 'platform_admin',
    'Migrated from users.is_platform_admin'
FROM migrated;

ALTER TABLE platform_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE platform_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_audit_events FORCE ROW LEVEL SECURITY;

REVOKE ALL ON platform_memberships FROM ucve_app;
REVOKE ALL ON platform_audit_events FROM ucve_app;
