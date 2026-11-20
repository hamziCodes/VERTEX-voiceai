"""PostgreSQL Studio repository with explicit platform and tenant transactions."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from control_plane.studio.models import (
    IdentityContext,
    OnboardingProfile,
    PlatformAuditAction,
    PlatformAuditEvent,
    PlatformRole,
    PlatformStaffMember,
    StudioRole,
    SupportScope,
    SupportSession,
    TenantDirectoryEntry,
    TenantDirectoryPage,
    TenantEntitlements,
    TenantSummary,
    UserIdentity,
    WorkspaceInvitation,
    WorkspaceMembership,
)
from control_plane.studio.repository import (
    IdentityConflictError,
    InvitationConsumedError,
    InvitationEmailMismatchError,
    InvitationExpiredError,
    InvitationNotFoundError,
    LastAdminError,
    LastPlatformAdminError,
    MembershipNotFoundError,
    StaffNotFoundError,
    SupportSessionClosedError,
    SupportSessionConflictError,
    SupportSessionNotFoundError,
    WorkspaceNotFoundError,
    parse_tenant_query,
    validate_audit_limit,
    validate_directory_window,
    validate_platform_reason,
    validate_platform_role,
    validate_support_list,
    validate_support_request,
)
from core.db.async_pg import AsyncDatabase, get_default_database

_ROLE_ADAPTER: TypeAdapter[StudioRole] = TypeAdapter(StudioRole)
_TOKEN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class PostgresStudioRepository:
    """Persist Studio identity and workspace state without exposing token hashes."""

    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    @staticmethod
    def _normalize_workspace_name(name: str) -> str:
        normalized = name.strip()
        if not normalized or len(normalized) > 255:
            raise ValueError("workspace name must contain 1 to 255 characters")
        return normalized

    @staticmethod
    def _normalize_email(email: str) -> str:
        normalized = email.strip().casefold()
        if not normalized or len(normalized) > 320:
            raise ValueError("invitation email is invalid")
        return normalized

    @staticmethod
    def _validate_hash(token_hash: str) -> str:
        normalized = token_hash.strip().lower()
        if _TOKEN_HASH_PATTERN.fullmatch(normalized) is None:
            raise ValueError(
                "invitation token hash must be 64 lowercase hex characters"
            )
        return normalized

    @staticmethod
    def _identity_from_row(row: Any) -> UserIdentity:
        return UserIdentity(
            user_id=row[0],
            issuer=row[1],
            subject=row[2],
            email=row[3],
            is_active=row[4],
            is_platform_admin=row[5],
        )

    @staticmethod
    def _membership_from_row(row: Any) -> WorkspaceMembership:
        return WorkspaceMembership(
            user_id=row[0],
            tenant_id=row[1],
            tenant_name=row[2],
            role=row[3],
            created_at=row[4],
        )

    @staticmethod
    def _invitation_from_row(row: Any) -> WorkspaceInvitation:
        return WorkspaceInvitation(
            invitation_id=row[0],
            tenant_id=row[1],
            email=row[2],
            role=row[3],
            invited_by=row[4],
            expires_at=row[5],
            accepted_at=row[6],
            accepted_by=row[7],
            created_at=row[8],
        )

    @staticmethod
    def _onboarding_from_row(row: Any) -> OnboardingProfile:
        return OnboardingProfile(
            tenant_id=row[0],
            business_name=row[1],
            use_case=row[2],
            languages=tuple(row[3]),
            operating_region=row[4],
            timezone=row[5],
            escalation_email=row[6],
            completed_steps=tuple(row[7]),
            updated_at=row[8],
        )

    @staticmethod
    def _entitlements_from_row(row: Any) -> TenantEntitlements:
        return TenantEntitlements(
            tenant_id=row[0],
            max_agents=row[1],
            max_concurrent_sessions=row[2],
            max_knowledge_bytes=row[3],
            api_keys_allowed=row[4],
            telephony_enabled=row[5],
            advanced_providers_enabled=row[6],
            byok_enabled=row[7],
            allowed_retention_days=tuple(row[8]),
            updated_at=row[9],
        )

    async def resolve_identity(self, identity: IdentityContext) -> UserIdentity:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT u.id, e.issuer, e.subject, u.email, u.is_active,
                    u.is_platform_admin
                FROM external_identities e
                JOIN users u ON u.id = e.user_id
                WHERE e.issuer = %s AND e.subject = %s
                FOR UPDATE OF e, u
                """,
                (identity.issuer, identity.subject),
            )
            row = await cursor.fetchone()
            if row is not None:
                await connection.execute(
                    """
                    UPDATE external_identities
                    SET email_snapshot = %s, last_seen_at = NOW()
                    WHERE issuer = %s AND subject = %s
                    """,
                    (identity.email, identity.issuer, identity.subject),
                )
                await connection.execute(
                    "UPDATE users SET email = %s WHERE id = %s",
                    (identity.email, row[0]),
                )
                return UserIdentity(
                    user_id=row[0],
                    issuer=row[1],
                    subject=row[2],
                    email=identity.email,
                    is_active=row[4],
                    is_platform_admin=row[5],
                )

            if identity.email is not None:
                cursor = await connection.execute(
                    "SELECT id FROM users WHERE LOWER(email) = %s",
                    (identity.email,),
                )
                if await cursor.fetchone() is not None:
                    raise IdentityConflictError(
                        "Email belongs to a different external identity."
                    )

            cursor = await connection.execute(
                """
                INSERT INTO users (email, password_hash, is_active)
                VALUES (%s, NULL, TRUE)
                RETURNING id, email, is_active, is_platform_admin
                """,
                (identity.email,),
            )
            user_row = await cursor.fetchone()
            if user_row is None:  # pragma: no cover - database contract failure
                raise RuntimeError("Identity insert returned no user.")
            await connection.execute(
                """
                INSERT INTO external_identities
                    (user_id, issuer, subject, email_snapshot)
                VALUES (%s, %s, %s, %s)
                """,
                (user_row[0], identity.issuer, identity.subject, identity.email),
            )
            return UserIdentity(
                user_id=user_row[0],
                issuer=identity.issuer,
                subject=identity.subject,
                email=user_row[1],
                is_active=user_row[2],
                is_platform_admin=user_row[3],
            )

    async def list_memberships(self, user_id: UUID) -> tuple[WorkspaceMembership, ...]:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT m.user_id, m.tenant_id, t.name, m.role, m.created_at
                FROM memberships m
                JOIN tenants t ON t.id = m.tenant_id
                WHERE m.user_id = %s AND t.deleted_at IS NULL
                ORDER BY LOWER(t.name), t.id
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
        return tuple(self._membership_from_row(row) for row in rows)

    async def list_workspace_members(
        self, tenant_id: UUID
    ) -> tuple[WorkspaceMembership, ...]:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT m.user_id, m.tenant_id, t.name, m.role, m.created_at
                FROM memberships m
                JOIN tenants t ON t.id = m.tenant_id
                WHERE m.tenant_id = %s AND t.deleted_at IS NULL
                ORDER BY m.role, m.user_id
                """,
                (tenant_id,),
            )
            rows = await cursor.fetchall()
            if not rows:
                cursor = await connection.execute(
                    "SELECT 1 FROM tenants WHERE id = %s AND deleted_at IS NULL",
                    (tenant_id,),
                )
                if await cursor.fetchone() is None:
                    raise WorkspaceNotFoundError("Workspace was not found.")
        return tuple(self._membership_from_row(row) for row in rows)

    async def create_workspace(
        self, owner_user_id: UUID, name: str
    ) -> WorkspaceMembership:
        normalized_name = self._normalize_workspace_name(name)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                "SELECT is_active FROM users WHERE id = %s FOR UPDATE",
                (owner_user_id,),
            )
            owner = await cursor.fetchone()
            if owner is None or not owner[0]:
                raise MembershipNotFoundError("Workspace owner identity was not found.")
            cursor = await connection.execute(
                "INSERT INTO tenants (name) VALUES (%s) RETURNING id",
                (normalized_name,),
            )
            tenant = await cursor.fetchone()
            if tenant is None:  # pragma: no cover - database contract failure
                raise RuntimeError("Workspace insert returned no tenant.")
            tenant_id = tenant[0]
            cursor = await connection.execute(
                """
                INSERT INTO memberships (user_id, tenant_id, role)
                VALUES (%s, %s, 'tenant_admin')
                RETURNING created_at
                """,
                (owner_user_id, tenant_id),
            )
            membership_row = await cursor.fetchone()
            await connection.execute(
                "INSERT INTO tenant_onboarding_profiles (tenant_id) VALUES (%s)",
                (tenant_id,),
            )
            await connection.execute(
                "INSERT INTO tenant_entitlements (tenant_id) VALUES (%s)",
                (tenant_id,),
            )
            if membership_row is None:  # pragma: no cover
                raise RuntimeError("Membership insert returned no row.")
            return WorkspaceMembership(
                user_id=owner_user_id,
                tenant_id=tenant_id,
                tenant_name=normalized_name,
                role="tenant_admin",
                created_at=membership_row[0],
            )

    async def create_invitation(
        self,
        tenant_id: UUID,
        *,
        email: str,
        role: StudioRole,
        token_hash: str,
        expires_at: datetime,
        invited_by: UUID,
    ) -> WorkspaceInvitation:
        normalized_email = self._normalize_email(email)
        normalized_hash = self._validate_hash(token_hash)
        validated_role = _ROLE_ADAPTER.validate_python(role)
        if expires_at.tzinfo is None:
            raise ValueError("invitation expiry must be timezone-aware")
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT role FROM memberships
                WHERE tenant_id = %s AND user_id = %s
                """,
                (tenant_id, invited_by),
            )
            inviter = await cursor.fetchone()
            if inviter is None or inviter[0] != "tenant_admin":
                raise PermissionError("Only tenant administrators may invite members.")
            cursor = await connection.execute(
                """
                INSERT INTO workspace_invitations
                    (tenant_id, email, role, token_hash, invited_by, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING invitation_id, tenant_id, email, role, invited_by,
                    expires_at, accepted_at, accepted_by, created_at
                """,
                (
                    tenant_id,
                    normalized_email,
                    validated_role,
                    normalized_hash,
                    invited_by,
                    expires_at,
                ),
            )
            row = await cursor.fetchone()
        if row is None:  # pragma: no cover
            raise RuntimeError("Invitation insert returned no row.")
        return self._invitation_from_row(row)

    async def accept_invitation(
        self, token_hash: str, user_id: UUID, *, now: datetime | None = None
    ) -> WorkspaceMembership:
        normalized_hash = self._validate_hash(token_hash)
        accepted_at = now or datetime.now(UTC)
        if accepted_at.tzinfo is None:
            raise ValueError("acceptance time must be timezone-aware")
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT invitation_id, tenant_id, email, role, expires_at,
                    accepted_at
                FROM workspace_invitations
                WHERE token_hash = %s
                FOR UPDATE
                """,
                (normalized_hash,),
            )
            invitation = await cursor.fetchone()
            if invitation is None:
                raise InvitationNotFoundError("Invitation was not found.")
            if invitation[5] is not None:
                raise InvitationConsumedError("Invitation was already accepted.")
            if accepted_at >= invitation[4]:
                raise InvitationExpiredError("Invitation has expired.")
            cursor = await connection.execute(
                "SELECT email, is_active FROM users WHERE id = %s FOR UPDATE",
                (user_id,),
            )
            user = await cursor.fetchone()
            if user is None or not user[1]:
                raise MembershipNotFoundError("Authenticated identity was not found.")
            if user[0] is None or user[0].casefold() != invitation[2].casefold():
                raise InvitationEmailMismatchError(
                    "Authenticated identity does not match invitation email."
                )
            await connection.execute(
                """
                INSERT INTO memberships (user_id, tenant_id, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, tenant_id) DO NOTHING
                """,
                (user_id, invitation[1], invitation[3]),
            )
            await connection.execute(
                """
                UPDATE workspace_invitations
                SET accepted_at = %s, accepted_by = %s
                WHERE invitation_id = %s
                """,
                (accepted_at, user_id, invitation[0]),
            )
            cursor = await connection.execute(
                """
                SELECT m.user_id, m.tenant_id, t.name, m.role, m.created_at
                FROM memberships m
                JOIN tenants t ON t.id = m.tenant_id
                WHERE m.tenant_id = %s AND m.user_id = %s
                """,
                (invitation[1], user_id),
            )
            membership = await cursor.fetchone()
        if membership is None:  # pragma: no cover
            raise RuntimeError("Accepted invitation returned no membership.")
        return self._membership_from_row(membership)

    async def set_member_role(
        self, tenant_id: UUID, user_id: UUID, role: StudioRole
    ) -> WorkspaceMembership:
        validated_role = _ROLE_ADAPTER.validate_python(role)
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT role, created_at FROM memberships
                WHERE tenant_id = %s AND user_id = %s
                FOR UPDATE
                """,
                (tenant_id, user_id),
            )
            current = await cursor.fetchone()
            if current is None:
                raise MembershipNotFoundError("Membership was not found.")
            if current[0] == "tenant_admin" and validated_role != "tenant_admin":
                cursor = await connection.execute(
                    """
                    SELECT COUNT(*) FROM memberships
                    WHERE tenant_id = %s AND role = 'tenant_admin'
                    """,
                    (tenant_id,),
                )
                count_row = await cursor.fetchone()
                if count_row is None or int(count_row[0]) <= 1:
                    raise LastAdminError(
                        "A workspace must retain one tenant administrator."
                    )
            await connection.execute(
                """
                UPDATE memberships SET role = %s
                WHERE tenant_id = %s AND user_id = %s
                """,
                (validated_role, tenant_id, user_id),
            )
            cursor = await connection.execute(
                "SELECT name FROM tenants WHERE id = %s",
                (tenant_id,),
            )
            tenant = await cursor.fetchone()
        if tenant is None:  # pragma: no cover
            raise WorkspaceNotFoundError("Workspace was not found.")
        return WorkspaceMembership(
            user_id=user_id,
            tenant_id=tenant_id,
            tenant_name=tenant[0],
            role=validated_role,
            created_at=current[1],
        )

    async def remove_member(self, tenant_id: UUID, user_id: UUID) -> None:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT role FROM memberships
                WHERE tenant_id = %s AND user_id = %s
                FOR UPDATE
                """,
                (tenant_id, user_id),
            )
            current = await cursor.fetchone()
            if current is None:
                raise MembershipNotFoundError("Membership was not found.")
            if current[0] == "tenant_admin":
                cursor = await connection.execute(
                    """
                    SELECT COUNT(*) FROM memberships
                    WHERE tenant_id = %s AND role = 'tenant_admin'
                    """,
                    (tenant_id,),
                )
                count_row = await cursor.fetchone()
                if count_row is None or int(count_row[0]) <= 1:
                    raise LastAdminError(
                        "A workspace must retain one tenant administrator."
                    )
            await connection.execute(
                "DELETE FROM memberships WHERE tenant_id = %s AND user_id = %s",
                (tenant_id, user_id),
            )

    async def get_onboarding(self, tenant_id: UUID) -> OnboardingProfile:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT tenant_id, business_name, use_case, languages,
                    operating_region, timezone, escalation_email,
                    completed_steps, updated_at
                FROM tenant_onboarding_profiles
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace was not found.")
        return self._onboarding_from_row(row)

    async def save_onboarding(self, profile: OnboardingProfile) -> OnboardingProfile:
        async with self.database.tenant_transaction(
            str(profile.tenant_id)
        ) as connection:
            cursor = await connection.execute(
                """
                UPDATE tenant_onboarding_profiles
                SET business_name = %s, use_case = %s, languages = %s,
                    operating_region = %s, timezone = %s,
                    escalation_email = %s, completed_steps = %s::jsonb,
                    updated_at = NOW()
                WHERE tenant_id = %s
                RETURNING tenant_id, business_name, use_case, languages,
                    operating_region, timezone, escalation_email,
                    completed_steps, updated_at
                """,
                (
                    profile.business_name,
                    profile.use_case,
                    list(profile.languages),
                    profile.operating_region,
                    profile.timezone,
                    profile.escalation_email,
                    json.dumps(profile.completed_steps),
                    profile.tenant_id,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace was not found.")
        return self._onboarding_from_row(row)

    async def get_entitlements(self, tenant_id: UUID) -> TenantEntitlements:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                """
                SELECT tenant_id, max_agents, max_concurrent_sessions,
                    max_knowledge_bytes, api_keys_allowed, telephony_enabled,
                    advanced_providers_enabled, byok_enabled,
                    allowed_retention_days, updated_at
                FROM tenant_entitlements
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace was not found.")
        return self._entitlements_from_row(row)

    async def save_entitlements(
        self, entitlements: TenantEntitlements
    ) -> TenantEntitlements:
        async with self.database.tenant_transaction(
            str(entitlements.tenant_id)
        ) as connection:
            cursor = await connection.execute(
                """
                UPDATE tenant_entitlements
                SET max_agents = %s, max_concurrent_sessions = %s,
                    max_knowledge_bytes = %s, api_keys_allowed = %s,
                    telephony_enabled = %s, advanced_providers_enabled = %s,
                    byok_enabled = %s, allowed_retention_days = %s,
                    updated_at = NOW()
                WHERE tenant_id = %s
                RETURNING tenant_id, max_agents, max_concurrent_sessions,
                    max_knowledge_bytes, api_keys_allowed, telephony_enabled,
                    advanced_providers_enabled, byok_enabled,
                    allowed_retention_days, updated_at
                """,
                (
                    entitlements.max_agents,
                    entitlements.max_concurrent_sessions,
                    entitlements.max_knowledge_bytes,
                    entitlements.api_keys_allowed,
                    entitlements.telephony_enabled,
                    entitlements.advanced_providers_enabled,
                    entitlements.byok_enabled,
                    list(entitlements.allowed_retention_days),
                    entitlements.tenant_id,
                ),
            )
            row = await cursor.fetchone()
        if row is None:
            raise WorkspaceNotFoundError("Workspace was not found.")
        return self._entitlements_from_row(row)

    # Phase 13J platform staff -------------------------------------------------
    #
    # Platform tables are not granted to ucve_app; every method below runs in
    # platform_transaction. Staff mutations lock the active administrator set
    # in a fixed order first, so concurrent revocations serialize and the
    # last-administrator check cannot be raced.

    _STAFF_SELECT = """
        SELECT p.user_id, u.email, p.role, p.granted_by, p.granted_at, p.reason
        FROM platform_memberships p
        JOIN users u ON u.id = p.user_id
    """

    @staticmethod
    def _staff_from_row(row: Any) -> PlatformStaffMember:
        return PlatformStaffMember(
            user_id=row[0],
            email=row[1],
            role=row[2],
            granted_by=row[3],
            granted_at=row[4],
            reason=row[5],
        )

    @staticmethod
    async def _record_platform_event(
        connection: Any,
        action: PlatformAuditAction,
        *,
        actor_user_id: UUID | None,
        target_user_id: UUID | None = None,
        target_tenant_id: UUID | None = None,
        previous_role: PlatformRole | None = None,
        new_role: PlatformRole | None = None,
        reason: str | None = None,
        support_session_id: UUID | None = None,
        scope: SupportScope | None = None,
    ) -> None:
        await connection.execute(
            """
            INSERT INTO platform_audit_events (
                actor_user_id, action, target_user_id, target_tenant_id,
                previous_role, new_role, reason, support_session_id, scope
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                actor_user_id,
                action,
                target_user_id,
                target_tenant_id,
                previous_role,
                new_role,
                reason,
                support_session_id,
                scope,
            ),
        )

    @staticmethod
    async def _lock_active_admins(connection: Any) -> set[UUID]:
        cursor = await connection.execute(
            """
            SELECT user_id FROM platform_memberships
            WHERE role = 'platform_admin' AND revoked_at IS NULL
            ORDER BY user_id
            FOR UPDATE
            """
        )
        return {row[0] for row in await cursor.fetchall()}

    async def get_platform_role(self, user_id: UUID) -> PlatformRole | None:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT p.role FROM platform_memberships p
                JOIN users u ON u.id = p.user_id
                WHERE p.user_id = %s AND p.revoked_at IS NULL AND u.is_active
                """,
                (user_id,),
            )
            row = await cursor.fetchone()
        return None if row is None else validate_platform_role(row[0])

    async def list_platform_staff(self) -> tuple[PlatformStaffMember, ...]:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                self._STAFF_SELECT
                + """
                WHERE p.revoked_at IS NULL
                ORDER BY p.role, u.email NULLS LAST, p.user_id
                """
            )
            rows = await cursor.fetchall()
        return tuple(self._staff_from_row(row) for row in rows)

    async def grant_platform_role(
        self,
        *,
        actor_user_id: UUID,
        email: str,
        role: PlatformRole,
        reason: str,
    ) -> PlatformStaffMember:
        validated_role = validate_platform_role(role)
        normalized_reason = validate_platform_reason(reason)
        normalized_email = self._normalize_email(email)
        async with self.database.platform_transaction() as connection:
            admins = await self._lock_active_admins(connection)
            if actor_user_id not in admins:
                raise PermissionError("Only platform administrators may manage staff.")
            cursor = await connection.execute(
                "SELECT id, is_active FROM users WHERE LOWER(email) = %s",
                (normalized_email,),
            )
            user = await cursor.fetchone()
            if user is None or not user[1]:
                raise StaffNotFoundError("No active Wavia user has that email.")
            target_id: UUID = user[0]
            cursor = await connection.execute(
                """
                SELECT role, revoked_at FROM platform_memberships
                WHERE user_id = %s
                FOR UPDATE
                """,
                (target_id,),
            )
            existing = await cursor.fetchone()
            previous: PlatformRole | None = (
                validate_platform_role(existing[0])
                if existing is not None and existing[1] is None
                else None
            )
            if previous != validated_role:
                if (
                    previous == "platform_admin"
                    and validated_role != "platform_admin"
                    and len(admins) <= 1
                ):
                    raise LastPlatformAdminError(
                        "Wavia must retain one platform administrator."
                    )
                await connection.execute(
                    """
                    INSERT INTO platform_memberships
                        (user_id, role, granted_by, granted_at, reason)
                    VALUES (%s, %s, %s, NOW(), %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        role = EXCLUDED.role,
                        granted_by = EXCLUDED.granted_by,
                        granted_at = EXCLUDED.granted_at,
                        reason = EXCLUDED.reason,
                        revoked_at = NULL,
                        revoked_by = NULL,
                        revoke_reason = NULL
                    """,
                    (target_id, validated_role, actor_user_id, normalized_reason),
                )
                await self._record_platform_event(
                    connection,
                    "platform_staff.role_changed"
                    if previous
                    else "platform_staff.granted",
                    actor_user_id=actor_user_id,
                    target_user_id=target_id,
                    previous_role=previous,
                    new_role=validated_role,
                    reason=normalized_reason,
                )
            cursor = await connection.execute(
                self._STAFF_SELECT + " WHERE p.user_id = %s",
                (target_id,),
            )
            row = await cursor.fetchone()
        if row is None:  # pragma: no cover - database contract failure
            raise RuntimeError("Platform grant returned no staff row.")
        return self._staff_from_row(row)

    async def revoke_platform_role(
        self, *, actor_user_id: UUID, user_id: UUID, reason: str
    ) -> None:
        normalized_reason = validate_platform_reason(reason)
        async with self.database.platform_transaction() as connection:
            admins = await self._lock_active_admins(connection)
            if actor_user_id not in admins:
                raise PermissionError("Only platform administrators may manage staff.")
            cursor = await connection.execute(
                """
                SELECT role FROM platform_memberships
                WHERE user_id = %s AND revoked_at IS NULL
                FOR UPDATE
                """,
                (user_id,),
            )
            current = await cursor.fetchone()
            if current is None:
                raise StaffNotFoundError("Platform staff assignment was not found.")
            previous = validate_platform_role(current[0])
            if previous == "platform_admin" and len(admins) <= 1:
                raise LastPlatformAdminError(
                    "Wavia must retain one platform administrator."
                )
            await connection.execute(
                """
                UPDATE platform_memberships
                SET revoked_at = NOW(), revoked_by = %s, revoke_reason = %s
                WHERE user_id = %s
                """,
                (actor_user_id, normalized_reason, user_id),
            )
            await self._record_platform_event(
                connection,
                "platform_staff.revoked",
                actor_user_id=actor_user_id,
                target_user_id=user_id,
                previous_role=previous,
                reason=normalized_reason,
            )

    async def list_tenant_directory(
        self, *, query: str | None, limit: int, offset: int
    ) -> TenantDirectoryPage:
        search, limit, offset = validate_directory_window(query, limit, offset)
        where = ""
        params: tuple[Any, ...] = ()
        if search is not None:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            where = "WHERE t.name ILIKE %s ESCAPE '\\'"
            params = (f"%{escaped}%",)
            exact = parse_tenant_query(search)
            if exact is not None:
                where += " OR t.id = %s"
                params = (*params, exact)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                f"SELECT COUNT(*) FROM tenants t {where}", params
            )
            total_row = await cursor.fetchone()
            cursor = await connection.execute(
                f"""
                SELECT t.id, t.name, t.created_at,
                    (SELECT COUNT(*) FROM memberships m WHERE m.tenant_id = t.id),
                    (SELECT COUNT(*) FROM agents a WHERE a.tenant_id = t.id)
                FROM tenants t
                {where}
                ORDER BY LOWER(t.name), t.id
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = await cursor.fetchall()
        return TenantDirectoryPage(
            items=tuple(
                TenantDirectoryEntry(
                    tenant_id=row[0],
                    name=row[1],
                    created_at=row[2],
                    member_count=int(row[3]),
                    agent_count=int(row[4]),
                )
                for row in rows
            ),
            total=int(total_row[0]) if total_row else 0,
            limit=limit,
            offset=offset,
        )

    async def view_tenant_summary(
        self, tenant_id: UUID, *, actor_user_id: UUID
    ) -> TenantSummary:
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT p.role FROM platform_memberships p
                JOIN users u ON u.id = p.user_id
                WHERE p.user_id = %s AND p.revoked_at IS NULL AND u.is_active
                """,
                (actor_user_id,),
            )
            if await cursor.fetchone() is None:
                raise PermissionError("Platform staff role is required.")
            cursor = await connection.execute(
                "SELECT id, name, created_at FROM tenants WHERE id = %s",
                (tenant_id,),
            )
            tenant = await cursor.fetchone()
            if tenant is None:
                raise WorkspaceNotFoundError("Workspace was not found.")
            cursor = await connection.execute(
                """
                SELECT role, COUNT(*) FROM memberships
                WHERE tenant_id = %s
                GROUP BY role
                ORDER BY role
                """,
                (tenant_id,),
            )
            counts = {
                _ROLE_ADAPTER.validate_python(row[0]): int(row[1])
                for row in await cursor.fetchall()
            }
            cursor = await connection.execute(
                "SELECT COUNT(*) FROM agents WHERE tenant_id = %s", (tenant_id,)
            )
            agents_row = await cursor.fetchone()
            cursor = await connection.execute(
                """
                SELECT tenant_id, max_agents, max_concurrent_sessions,
                    max_knowledge_bytes, api_keys_allowed, telephony_enabled,
                    advanced_providers_enabled, byok_enabled,
                    allowed_retention_days, updated_at
                FROM tenant_entitlements
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            entitlements_row = await cursor.fetchone()
            cursor = await connection.execute(
                """
                SELECT completed_steps FROM tenant_onboarding_profiles
                WHERE tenant_id = %s
                """,
                (tenant_id,),
            )
            onboarding_row = await cursor.fetchone()
            await self._record_platform_event(
                connection,
                "platform_tenant.viewed",
                actor_user_id=actor_user_id,
                target_tenant_id=tenant_id,
            )
        return TenantSummary(
            tenant_id=tenant[0],
            name=tenant[1],
            created_at=tenant[2],
            members_by_role=counts,
            agent_count=int(agents_row[0]) if agents_row else 0,
            entitlements=(
                self._entitlements_from_row(entitlements_row)
                if entitlements_row is not None
                else None
            ),
            onboarding_completed_steps=(
                tuple(onboarding_row[0]) if onboarding_row is not None else ()
            ),
        )

    async def list_platform_audit(
        self, *, limit: int
    ) -> tuple[PlatformAuditEvent, ...]:
        limit = validate_audit_limit(limit)
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                """
                SELECT event_id, actor_user_id, action, target_user_id,
                    target_tenant_id, previous_role, new_role, reason, created_at,
                    support_session_id, scope
                FROM platform_audit_events
                ORDER BY created_at DESC, event_id DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return tuple(
            PlatformAuditEvent(
                event_id=row[0],
                actor_user_id=row[1],
                action=row[2],
                target_user_id=row[3],
                target_tenant_id=row[4],
                previous_role=row[5],
                new_role=row[6],
                reason=row[7],
                created_at=row[8],
                support_session_id=row[9],
                scope=row[10],
            )
            for row in rows
        )

    # Phase 13K support sessions ----------------------------------------------
    #
    # Session state is computed from the database clock (NOW() at transaction
    # start), so expiry never depends on the application server's clock.

    _SUPPORT_SELECT = """
        SELECT s.session_id, s.actor_user_id, u.email, s.tenant_id, t.name,
            s.reason, s.reference, s.scopes, s.created_at, s.expires_at,
            s.ended_at, s.ended_by, s.end_reason,
            CASE
                WHEN s.ended_at IS NOT NULL THEN 'ended'
                WHEN NOW() >= s.expires_at THEN 'expired'
                ELSE 'active'
            END
        FROM platform_support_sessions s
        JOIN users u ON u.id = s.actor_user_id
        JOIN tenants t ON t.id = s.tenant_id
    """

    @staticmethod
    def _support_from_row(row: Any) -> SupportSession:
        return SupportSession(
            session_id=row[0],
            actor_user_id=row[1],
            actor_email=row[2],
            tenant_id=row[3],
            tenant_name=row[4],
            reason=row[5],
            reference=row[6],
            scopes=tuple(row[7]),
            created_at=row[8],
            expires_at=row[9],
            ended_at=row[10],
            ended_by=row[11],
            end_reason=row[12],
            state=row[13],
        )

    @staticmethod
    async def _has_active_platform_role(connection: Any, user_id: UUID) -> bool:
        cursor = await connection.execute(
            """
            SELECT 1 FROM platform_memberships p
            JOIN users u ON u.id = p.user_id
            WHERE p.user_id = %s AND p.revoked_at IS NULL AND u.is_active
            """,
            (user_id,),
        )
        return await cursor.fetchone() is not None

    async def _select_support(
        self, connection: Any, session_id: UUID, *, lock: bool = False
    ) -> SupportSession:
        cursor = await connection.execute(
            self._SUPPORT_SELECT
            + " WHERE s.session_id = %s"
            + (" FOR UPDATE OF s" if lock else ""),
            (session_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            raise SupportSessionNotFoundError("Support session was not found.")
        return self._support_from_row(row)

    async def start_support_session(
        self,
        *,
        actor_user_id: UUID,
        tenant_id: UUID,
        reason: str,
        reference: str | None,
        scopes: tuple[SupportScope, ...],
        duration_minutes: int,
    ) -> SupportSession:
        normalized_reason, normalized_reference, ordered = validate_support_request(
            reason, reference, scopes, duration_minutes
        )
        async with self.database.platform_transaction() as connection:
            if not await self._has_active_platform_role(connection, actor_user_id):
                raise PermissionError("Platform staff role is required.")
            cursor = await connection.execute(
                "SELECT 1 FROM tenants WHERE id = %s", (tenant_id,)
            )
            if await cursor.fetchone() is None:
                raise WorkspaceNotFoundError("Workspace was not found.")
            # Serialize concurrent starts for the same staff member and tenant.
            await connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"support:{actor_user_id}:{tenant_id}",),
            )
            cursor = await connection.execute(
                """
                SELECT 1 FROM platform_support_sessions
                WHERE actor_user_id = %s AND tenant_id = %s
                    AND ended_at IS NULL AND expires_at > NOW()
                """,
                (actor_user_id, tenant_id),
            )
            if await cursor.fetchone() is not None:
                raise SupportSessionConflictError(
                    "You already have an active support session for this tenant."
                )
            cursor = await connection.execute(
                """
                INSERT INTO platform_support_sessions
                    (actor_user_id, tenant_id, reason, reference, scopes, expires_at)
                VALUES (%s, %s, %s, %s, %s, NOW() + make_interval(mins => %s))
                RETURNING session_id
                """,
                (
                    actor_user_id,
                    tenant_id,
                    normalized_reason,
                    normalized_reference,
                    list(ordered),
                    duration_minutes,
                ),
            )
            created = await cursor.fetchone()
            if created is None:  # pragma: no cover - database contract failure
                raise RuntimeError("Support session insert returned no row.")
            await self._record_platform_event(
                connection,
                "platform_support.session_started",
                actor_user_id=actor_user_id,
                target_tenant_id=tenant_id,
                reason=normalized_reason,
                support_session_id=created[0],
            )
            return await self._select_support(connection, created[0])

    async def get_support_session(self, session_id: UUID) -> SupportSession:
        async with self.database.platform_transaction() as connection:
            return await self._select_support(connection, session_id)

    async def list_support_sessions(
        self, *, state: str, limit: int
    ) -> tuple[SupportSession, ...]:
        limit = validate_support_list(limit)
        if state not in ("active", "recent"):
            raise ValueError("state must be active or recent")
        where = (
            " WHERE s.ended_at IS NULL AND s.expires_at > NOW()"
            if state == "active"
            else ""
        )
        async with self.database.platform_transaction() as connection:
            cursor = await connection.execute(
                self._SUPPORT_SELECT
                + where
                + " ORDER BY s.created_at DESC, s.session_id DESC LIMIT %s",
                (limit,),
            )
            rows = await cursor.fetchall()
        return tuple(self._support_from_row(row) for row in rows)

    async def end_support_session(
        self,
        *,
        actor_user_id: UUID,
        session_id: UUID,
        reason: str | None,
        may_end_any: bool,
    ) -> SupportSession:
        normalized_reason = (
            validate_platform_reason(reason) if reason and reason.strip() else None
        )
        async with self.database.platform_transaction() as connection:
            session = await self._select_support(connection, session_id, lock=True)
            if not await self._has_active_platform_role(connection, actor_user_id):
                raise PermissionError("Platform staff role is required.")
            if session.actor_user_id != actor_user_id and not may_end_any:
                raise PermissionError("Only the session owner may end this session.")
            if session.state != "active":
                raise SupportSessionClosedError("Support session is already closed.")
            await connection.execute(
                """
                UPDATE platform_support_sessions
                SET ended_at = NOW(), ended_by = %s, end_reason = %s
                WHERE session_id = %s
                """,
                (actor_user_id, normalized_reason, session_id),
            )
            await self._record_platform_event(
                connection,
                "platform_support.session_ended",
                actor_user_id=actor_user_id,
                target_tenant_id=session.tenant_id,
                reason=normalized_reason,
                support_session_id=session_id,
            )
            return await self._select_support(connection, session_id)

    async def authorize_support_read(
        self, *, actor_user_id: UUID, session_id: UUID, scope: SupportScope
    ) -> SupportSession:
        async with self.database.platform_transaction() as connection:
            session = await self._select_support(connection, session_id)
            if session.actor_user_id != actor_user_id or not (
                await self._has_active_platform_role(connection, actor_user_id)
            ):
                raise PermissionError("Only the session owner may read through it.")
            if session.state != "active":
                raise SupportSessionClosedError("Support session is closed.")
            if scope not in session.scopes:
                raise PermissionError("This support session does not grant that scope.")
            await self._record_platform_event(
                connection,
                "platform_support.data_viewed",
                actor_user_id=actor_user_id,
                target_tenant_id=session.tenant_id,
                support_session_id=session_id,
                scope=scope,
            )
            return session
