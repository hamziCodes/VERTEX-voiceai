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
    StudioRole,
    TenantEntitlements,
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
    MembershipNotFoundError,
    WorkspaceNotFoundError,
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
