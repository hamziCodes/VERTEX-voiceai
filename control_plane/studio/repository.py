"""Studio repository contracts and deterministic in-memory implementation."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

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

_ROLE_ADAPTER: TypeAdapter[StudioRole] = TypeAdapter(StudioRole)
_TOKEN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class StudioRepositoryError(RuntimeError):
    """Base error for Studio persistence invariants."""


class IdentityConflictError(StudioRepositoryError):
    """An email already belongs to a different external identity."""


class WorkspaceNotFoundError(StudioRepositoryError):
    """The requested workspace does not exist."""


class MembershipNotFoundError(StudioRepositoryError):
    """The requested membership does not exist."""


class InvitationNotFoundError(StudioRepositoryError):
    """The invitation hash is unknown."""


class InvitationExpiredError(StudioRepositoryError):
    """The invitation expired before acceptance."""


class InvitationConsumedError(StudioRepositoryError):
    """The invitation was already accepted."""


class InvitationEmailMismatchError(StudioRepositoryError):
    """The authenticated identity does not match the invited email."""


class LastAdminError(StudioRepositoryError):
    """An operation would leave a workspace without a tenant administrator."""


class StudioRepository(Protocol):
    async def resolve_identity(self, identity: IdentityContext) -> UserIdentity: ...

    async def list_memberships(
        self, user_id: UUID
    ) -> tuple[WorkspaceMembership, ...]: ...

    async def list_workspace_members(
        self, tenant_id: UUID
    ) -> tuple[WorkspaceMembership, ...]: ...

    async def create_workspace(
        self, owner_user_id: UUID, name: str
    ) -> WorkspaceMembership: ...

    async def create_invitation(
        self,
        tenant_id: UUID,
        *,
        email: str,
        role: StudioRole,
        token_hash: str,
        expires_at: datetime,
        invited_by: UUID,
    ) -> WorkspaceInvitation: ...

    async def accept_invitation(
        self, token_hash: str, user_id: UUID, *, now: datetime | None = None
    ) -> WorkspaceMembership: ...

    async def set_member_role(
        self, tenant_id: UUID, user_id: UUID, role: StudioRole
    ) -> WorkspaceMembership: ...

    async def remove_member(self, tenant_id: UUID, user_id: UUID) -> None: ...

    async def get_onboarding(self, tenant_id: UUID) -> OnboardingProfile: ...

    async def save_onboarding(
        self, profile: OnboardingProfile
    ) -> OnboardingProfile: ...

    async def get_entitlements(self, tenant_id: UUID) -> TenantEntitlements: ...

    async def save_entitlements(
        self, entitlements: TenantEntitlements
    ) -> TenantEntitlements: ...


@dataclass(slots=True)
class _InvitationState:
    invitation: WorkspaceInvitation
    token_hash: str = field(repr=False)


class InMemoryStudioRepository:
    """Atomic in-memory repository for local development and unit tests."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._identities: dict[tuple[str, str], UserIdentity] = {}
        self._users: dict[UUID, UserIdentity] = {}
        self._tenants: dict[UUID, str] = {}
        self._memberships: dict[tuple[UUID, UUID], WorkspaceMembership] = {}
        self._invitations: dict[str, _InvitationState] = {}
        self._onboarding: dict[UUID, OnboardingProfile] = {}
        self._entitlements: dict[UUID, TenantEntitlements] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

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

    def safe_identity_snapshot(self) -> tuple[UserIdentity, ...]:
        return tuple(
            sorted(self._users.values(), key=lambda identity: str(identity.user_id))
        )

    async def resolve_identity(self, identity: IdentityContext) -> UserIdentity:
        key = (identity.issuer, identity.subject)
        async with self._lock:
            existing = self._identities.get(key)
            if existing is not None:
                updated = existing.model_copy(update={"email": identity.email})
                self._identities[key] = updated
                self._users[updated.user_id] = updated
                return updated
            if identity.email is not None and any(
                user.email == identity.email for user in self._users.values()
            ):
                raise IdentityConflictError(
                    "Email belongs to a different external identity."
                )
            created = UserIdentity(
                user_id=uuid4(),
                issuer=identity.issuer,
                subject=identity.subject,
                email=identity.email,
            )
            self._identities[key] = created
            self._users[created.user_id] = created
            return created

    async def list_memberships(self, user_id: UUID) -> tuple[WorkspaceMembership, ...]:
        async with self._lock:
            memberships = [
                membership
                for (tenant_id, member_id), membership in self._memberships.items()
                if member_id == user_id and tenant_id in self._tenants
            ]
            return tuple(
                sorted(
                    memberships,
                    key=lambda item: (item.tenant_name, str(item.tenant_id)),
                )
            )

    async def list_workspace_members(
        self, tenant_id: UUID
    ) -> tuple[WorkspaceMembership, ...]:
        async with self._lock:
            if tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            memberships = [
                membership
                for (member_tenant, _), membership in self._memberships.items()
                if member_tenant == tenant_id
            ]
            return tuple(
                sorted(memberships, key=lambda item: (item.role, str(item.user_id)))
            )

    async def create_workspace(
        self, owner_user_id: UUID, name: str
    ) -> WorkspaceMembership:
        normalized_name = self._normalize_workspace_name(name)
        async with self._lock:
            if owner_user_id not in self._users:
                raise MembershipNotFoundError("Workspace owner identity was not found.")
            tenant_id = uuid4()
            now = self._now()
            membership = WorkspaceMembership(
                user_id=owner_user_id,
                tenant_id=tenant_id,
                tenant_name=normalized_name,
                role="tenant_admin",
                created_at=now,
            )
            self._tenants[tenant_id] = normalized_name
            self._memberships[(tenant_id, owner_user_id)] = membership
            self._onboarding[tenant_id] = OnboardingProfile(tenant_id=tenant_id)
            self._entitlements[tenant_id] = TenantEntitlements(tenant_id=tenant_id)
            return membership

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
        async with self._lock:
            if tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            inviter = self._memberships.get((tenant_id, invited_by))
            if inviter is None or inviter.role != "tenant_admin":
                raise PermissionError("Only tenant administrators may invite members.")
            if normalized_hash in self._invitations:
                raise ValueError("invitation token hash already exists")
            invitation = WorkspaceInvitation(
                invitation_id=uuid4(),
                tenant_id=tenant_id,
                email=normalized_email,
                role=validated_role,
                invited_by=invited_by,
                expires_at=expires_at,
                created_at=self._now(),
            )
            self._invitations[normalized_hash] = _InvitationState(
                invitation=invitation,
                token_hash=normalized_hash,
            )
            return invitation

    async def accept_invitation(
        self, token_hash: str, user_id: UUID, *, now: datetime | None = None
    ) -> WorkspaceMembership:
        normalized_hash = self._validate_hash(token_hash)
        accepted_at = now or self._now()
        if accepted_at.tzinfo is None:
            raise ValueError("acceptance time must be timezone-aware")
        async with self._lock:
            state = self._invitations.get(normalized_hash)
            if state is None:
                raise InvitationNotFoundError("Invitation was not found.")
            invitation = state.invitation
            if invitation.accepted_at is not None:
                raise InvitationConsumedError("Invitation was already accepted.")
            if accepted_at >= invitation.expires_at:
                raise InvitationExpiredError("Invitation has expired.")
            identity = self._users.get(user_id)
            if identity is None:
                raise MembershipNotFoundError("Authenticated identity was not found.")
            if identity.email is None or identity.email != invitation.email:
                raise InvitationEmailMismatchError(
                    "Authenticated identity does not match invitation email."
                )
            membership = WorkspaceMembership(
                user_id=user_id,
                tenant_id=invitation.tenant_id,
                tenant_name=self._tenants[invitation.tenant_id],
                role=invitation.role,
                created_at=accepted_at,
            )
            self._memberships[(invitation.tenant_id, user_id)] = membership
            state.invitation = invitation.model_copy(
                update={"accepted_at": accepted_at, "accepted_by": user_id}
            )
            return membership

    def _admin_count(self, tenant_id: UUID) -> int:
        return sum(
            membership.role == "tenant_admin"
            for (member_tenant, _), membership in self._memberships.items()
            if member_tenant == tenant_id
        )

    async def set_member_role(
        self, tenant_id: UUID, user_id: UUID, role: StudioRole
    ) -> WorkspaceMembership:
        validated_role = _ROLE_ADAPTER.validate_python(role)
        async with self._lock:
            current = self._memberships.get((tenant_id, user_id))
            if current is None:
                raise MembershipNotFoundError("Membership was not found.")
            if (
                current.role == "tenant_admin"
                and validated_role != "tenant_admin"
                and self._admin_count(tenant_id) == 1
            ):
                raise LastAdminError(
                    "A workspace must retain one tenant administrator."
                )
            updated = current.model_copy(update={"role": validated_role})
            self._memberships[(tenant_id, user_id)] = updated
            return updated

    async def remove_member(self, tenant_id: UUID, user_id: UUID) -> None:
        async with self._lock:
            current = self._memberships.get((tenant_id, user_id))
            if current is None:
                raise MembershipNotFoundError("Membership was not found.")
            if current.role == "tenant_admin" and self._admin_count(tenant_id) == 1:
                raise LastAdminError(
                    "A workspace must retain one tenant administrator."
                )
            del self._memberships[(tenant_id, user_id)]

    async def get_onboarding(self, tenant_id: UUID) -> OnboardingProfile:
        async with self._lock:
            try:
                return self._onboarding[tenant_id]
            except KeyError as exc:
                raise WorkspaceNotFoundError("Workspace was not found.") from exc

    async def save_onboarding(self, profile: OnboardingProfile) -> OnboardingProfile:
        async with self._lock:
            if profile.tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            saved = profile.model_copy(update={"updated_at": self._now()})
            self._onboarding[profile.tenant_id] = saved
            return saved

    async def get_entitlements(self, tenant_id: UUID) -> TenantEntitlements:
        async with self._lock:
            try:
                return self._entitlements[tenant_id]
            except KeyError as exc:
                raise WorkspaceNotFoundError("Workspace was not found.") from exc

    async def save_entitlements(
        self, entitlements: TenantEntitlements
    ) -> TenantEntitlements:
        async with self._lock:
            if entitlements.tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            saved = entitlements.model_copy(update={"updated_at": self._now()})
            self._entitlements[entitlements.tenant_id] = saved
            return saved
