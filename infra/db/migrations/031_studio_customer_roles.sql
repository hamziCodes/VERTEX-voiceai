-- Keep Studio human membership and invitation roles aligned with launch RBAC.

ALTER TABLE memberships
    DROP CONSTRAINT IF EXISTS memberships_role_check,
    ADD CONSTRAINT memberships_role_check CHECK (
        role IN (
            'tenant_admin',
            'tenant_editor',
            'tenant_developer',
            'tenant_viewer',
            'compliance_admin'
        )
    ) NOT VALID;

ALTER TABLE memberships
    VALIDATE CONSTRAINT memberships_role_check;

ALTER TABLE workspace_invitations
    DROP CONSTRAINT IF EXISTS workspace_invitations_role_check,
    ADD CONSTRAINT workspace_invitations_role_check CHECK (
        role IN (
            'tenant_admin',
            'tenant_editor',
            'tenant_developer',
            'tenant_viewer',
            'compliance_admin'
        )
    ) NOT VALID;

ALTER TABLE workspace_invitations
    VALIDATE CONSTRAINT workspace_invitations_role_check;
