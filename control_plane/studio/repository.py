"""Studio repository contracts and deterministic in-memory implementation."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from control_plane.studio.models import (
    SUPPORT_SCOPES,
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

_ROLE_ADAPTER: TypeAdapter[StudioRole] = TypeAdapter(StudioRole)
_PLATFORM_ROLE_ADAPTER: TypeAdapter[PlatformRole] = TypeAdapter(PlatformRole)
DIRECTORY_MAX_LIMIT = 50
DIRECTORY_MAX_OFFSET = 10_000
DIRECTORY_MAX_QUERY = 255
PLATFORM_AUDIT_MAX_LIMIT = 100
REASON_MIN_LENGTH = 8
REASON_MAX_LENGTH = 500
SUPPORT_DURATIONS_MINUTES = (15, 30, 60)
SUPPORT_REFERENCE_MAX_LENGTH = 64
SUPPORT_LIST_MAX_LIMIT = 100
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


class LastPlatformAdminError(StudioRepositoryError):
    """An operation would leave Wavia without an active platform administrator."""


class StaffNotFoundError(StudioRepositoryError):
    """The user or active platform staff assignment does not exist."""


class SupportSessionNotFoundError(StudioRepositoryError):
    """The support session does not exist."""


class SupportSessionClosedError(StudioRepositoryError):
    """The support session has expired or was ended."""


class SupportSessionConflictError(StudioRepositoryError):
    """The staff member already has an active session for this tenant."""


def validate_support_request(
    reason: str,
    reference: str | None,
    scopes: tuple[str, ...] | list[str],
    duration_minutes: int,
) -> tuple[str, str | None, tuple[SupportScope, ...]]:
    """Validate a support-session request; scopes come back de-duplicated, ordered."""

    normalized_reason = validate_platform_reason(reason)
    normalized_reference = (reference or "").strip() or None
    if (
        normalized_reference is not None
        and len(normalized_reference) > SUPPORT_REFERENCE_MAX_LENGTH
    ):
        raise ValueError("reference must be at most 64 characters")
    requested = set(scopes)
    if not requested or not requested <= set(SUPPORT_SCOPES):
        raise ValueError("choose at least one supported read scope")
    if duration_minutes not in SUPPORT_DURATIONS_MINUTES:
        raise ValueError("duration must be 15, 30 or 60 minutes")
    ordered = tuple(scope for scope in SUPPORT_SCOPES if scope in requested)
    return normalized_reason, normalized_reference, ordered


def validate_support_list(limit: int) -> int:
    if not 1 <= limit <= SUPPORT_LIST_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {SUPPORT_LIST_MAX_LIMIT}")
    return limit


def validate_platform_reason(reason: str) -> str:
    """Return a whitespace-normalized reason or raise ValueError."""

    normalized = " ".join(reason.split())
    if not REASON_MIN_LENGTH <= len(normalized) <= REASON_MAX_LENGTH:
        raise ValueError(
            f"reason must contain {REASON_MIN_LENGTH} to {REASON_MAX_LENGTH} characters"
        )
    return normalized


def validate_platform_role(role: str) -> PlatformRole:
    try:
        return _PLATFORM_ROLE_ADAPTER.validate_python(role)
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        raise ValueError("unknown platform role") from exc


def validate_directory_window(
    query: str | None, limit: int, offset: int
) -> tuple[str | None, int, int]:
    if not 1 <= limit <= DIRECTORY_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {DIRECTORY_MAX_LIMIT}")
    if not 0 <= offset <= DIRECTORY_MAX_OFFSET:
        raise ValueError(f"offset must be between 0 and {DIRECTORY_MAX_OFFSET}")
    normalized = (query or "").strip()
    if len(normalized) > DIRECTORY_MAX_QUERY:
        raise ValueError("search must be at most 255 characters")
    return (normalized or None), limit, offset


def validate_audit_limit(limit: int) -> int:
    if not 1 <= limit <= PLATFORM_AUDIT_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {PLATFORM_AUDIT_MAX_LIMIT}")
    return limit


def parse_tenant_query(query: str) -> UUID | None:
    """Return a UUID when the search is an exact tenant identifier."""

    try:
        return UUID(query)
    except ValueError:
        return None


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

    async def get_platform_role(self, user_id: UUID) -> PlatformRole | None: ...

    async def list_platform_staff(self) -> tuple[PlatformStaffMember, ...]: ...

    async def grant_platform_role(
        self,
        *,
        actor_user_id: UUID,
        email: str,
        role: PlatformRole,
        reason: str,
    ) -> PlatformStaffMember: ...

    async def revoke_platform_role(
        self, *, actor_user_id: UUID, user_id: UUID, reason: str
    ) -> None: ...

    async def list_tenant_directory(
        self, *, query: str | None, limit: int, offset: int
    ) -> TenantDirectoryPage: ...

    async def view_tenant_summary(
        self, tenant_id: UUID, *, actor_user_id: UUID
    ) -> TenantSummary: ...

    async def list_platform_audit(
        self, *, limit: int
    ) -> tuple[PlatformAuditEvent, ...]: ...

    async def start_support_session(
        self,
        *,
        actor_user_id: UUID,
        tenant_id: UUID,
        reason: str,
        reference: str | None,
        scopes: tuple[SupportScope, ...],
        duration_minutes: int,
    ) -> SupportSession: ...

    async def get_support_session(self, session_id: UUID) -> SupportSession: ...

    async def list_support_sessions(
        self, *, state: str, limit: int
    ) -> tuple[SupportSession, ...]: ...

    async def end_support_session(
        self,
        *,
        actor_user_id: UUID,
        session_id: UUID,
        reason: str | None,
        may_end_any: bool,
    ) -> SupportSession: ...

    async def authorize_support_read(
        self, *, actor_user_id: UUID, session_id: UUID, scope: SupportScope
    ) -> SupportSession: ...


@dataclass(slots=True)
class _InvitationState:
    invitation: WorkspaceInvitation
    token_hash: str = field(repr=False)


@dataclass(slots=True)
class _SupportRecord:
    session_id: UUID
    actor_user_id: UUID
    tenant_id: UUID
    reason: str
    reference: str | None
    scopes: tuple[SupportScope, ...]
    created_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None
    ended_by: UUID | None = None
    end_reason: str | None = None


@dataclass(slots=True)
class _PlatformAssignment:
    role: PlatformRole
    granted_by: UUID | None
    granted_at: datetime
    reason: str
    revoked_at: datetime | None = None


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
        self._tenant_created: dict[UUID, datetime] = {}
        self._platform: dict[UUID, _PlatformAssignment] = {}
        self._platform_audit: list[PlatformAuditEvent] = []
        self._support: dict[UUID, _SupportRecord] = {}

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
            self._tenant_created[tenant_id] = now
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

    # Phase 13J platform staff -------------------------------------------------

    def _active_platform_role(self, user_id: UUID) -> PlatformRole | None:
        assignment = self._platform.get(user_id)
        if assignment is None or assignment.revoked_at is not None:
            return None
        return assignment.role

    def _active_admin_count(self) -> int:
        return sum(
            assignment.revoked_at is None and assignment.role == "platform_admin"
            for assignment in self._platform.values()
        )

    def _audit(
        self,
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
        self._platform_audit.append(
            PlatformAuditEvent(
                event_id=uuid4(),
                actor_user_id=actor_user_id,
                action=action,
                target_user_id=target_user_id,
                target_tenant_id=target_tenant_id,
                previous_role=previous_role,
                new_role=new_role,
                reason=reason,
                support_session_id=support_session_id,
                scope=scope,
                created_at=self._now(),
            )
        )

    def _require_platform_admin(self, actor_user_id: UUID) -> None:
        if self._active_platform_role(actor_user_id) != "platform_admin":
            raise PermissionError("Only platform administrators may manage staff.")

    def _staff_member(self, user_id: UUID) -> PlatformStaffMember:
        assignment = self._platform[user_id]
        user = self._users.get(user_id)
        return PlatformStaffMember(
            user_id=user_id,
            email=user.email if user is not None else None,
            role=assignment.role,
            granted_by=assignment.granted_by,
            granted_at=assignment.granted_at,
            reason=assignment.reason,
        )

    async def bootstrap_platform_admin(self, user_id: UUID, *, reason: str) -> None:
        """In-memory only: seed the first administrator (operators use SQL)."""

        normalized = validate_platform_reason(reason)
        async with self._lock:
            if user_id not in self._users:
                raise StaffNotFoundError("User was not found.")
            self._platform[user_id] = _PlatformAssignment(
                role="platform_admin",
                granted_by=None,
                granted_at=self._now(),
                reason=normalized,
            )

    async def get_platform_role(self, user_id: UUID) -> PlatformRole | None:
        async with self._lock:
            return self._active_platform_role(user_id)

    async def list_platform_staff(self) -> tuple[PlatformStaffMember, ...]:
        async with self._lock:
            members = [
                self._staff_member(user_id)
                for user_id, assignment in self._platform.items()
                if assignment.revoked_at is None
            ]
        return tuple(
            sorted(
                members,
                key=lambda item: (item.role, item.email or "", str(item.user_id)),
            )
        )

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
        async with self._lock:
            self._require_platform_admin(actor_user_id)
            target = next(
                (
                    user
                    for user in self._users.values()
                    if user.email == normalized_email
                ),
                None,
            )
            if target is None or not target.is_active:
                raise StaffNotFoundError("No active Wavia user has that email.")
            previous = self._active_platform_role(target.user_id)
            if previous == validated_role:
                return self._staff_member(target.user_id)
            if (
                previous == "platform_admin"
                and validated_role != "platform_admin"
                and self._active_admin_count() <= 1
            ):
                raise LastPlatformAdminError(
                    "Wavia must retain one platform administrator."
                )
            self._platform[target.user_id] = _PlatformAssignment(
                role=validated_role,
                granted_by=actor_user_id,
                granted_at=self._now(),
                reason=normalized_reason,
            )
            self._audit(
                "platform_staff.role_changed" if previous else "platform_staff.granted",
                actor_user_id=actor_user_id,
                target_user_id=target.user_id,
                previous_role=previous,
                new_role=validated_role,
                reason=normalized_reason,
            )
            return self._staff_member(target.user_id)

    async def revoke_platform_role(
        self, *, actor_user_id: UUID, user_id: UUID, reason: str
    ) -> None:
        normalized_reason = validate_platform_reason(reason)
        async with self._lock:
            self._require_platform_admin(actor_user_id)
            previous = self._active_platform_role(user_id)
            if previous is None:
                raise StaffNotFoundError("Platform staff assignment was not found.")
            if previous == "platform_admin" and self._active_admin_count() <= 1:
                raise LastPlatformAdminError(
                    "Wavia must retain one platform administrator."
                )
            self._platform[user_id].revoked_at = self._now()
            self._audit(
                "platform_staff.revoked",
                actor_user_id=actor_user_id,
                target_user_id=user_id,
                previous_role=previous,
                reason=normalized_reason,
            )

    def _directory_entry(self, tenant_id: UUID) -> TenantDirectoryEntry:
        return TenantDirectoryEntry(
            tenant_id=tenant_id,
            name=self._tenants[tenant_id],
            created_at=self._tenant_created[tenant_id],
            member_count=sum(
                member_tenant == tenant_id for member_tenant, _ in self._memberships
            ),
            # Agents are not tracked by this repository: report unknown, not zero.
            agent_count=None,
        )

    async def list_tenant_directory(
        self, *, query: str | None, limit: int, offset: int
    ) -> TenantDirectoryPage:
        search, limit, offset = validate_directory_window(query, limit, offset)
        async with self._lock:
            tenant_ids = list(self._tenants)
            if search is not None:
                exact = parse_tenant_query(search)
                needle = search.casefold()
                tenant_ids = [
                    tenant_id
                    for tenant_id in tenant_ids
                    if tenant_id == exact
                    or needle in self._tenants[tenant_id].casefold()
                ]
            tenant_ids.sort(
                key=lambda item: (self._tenants[item].casefold(), str(item))
            )
            window = tenant_ids[offset : offset + limit]
            return TenantDirectoryPage(
                items=tuple(self._directory_entry(item) for item in window),
                total=len(tenant_ids),
                limit=limit,
                offset=offset,
            )

    async def view_tenant_summary(
        self, tenant_id: UUID, *, actor_user_id: UUID
    ) -> TenantSummary:
        async with self._lock:
            if self._active_platform_role(actor_user_id) is None:
                raise PermissionError("Platform staff role is required.")
            if tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            counts: dict[StudioRole, int] = {}
            for (member_tenant, _), membership in self._memberships.items():
                if member_tenant == tenant_id:
                    counts[membership.role] = counts.get(membership.role, 0) + 1
            onboarding = self._onboarding.get(tenant_id)
            summary = TenantSummary(
                tenant_id=tenant_id,
                name=self._tenants[tenant_id],
                created_at=self._tenant_created[tenant_id],
                members_by_role=dict(sorted(counts.items())),
                agent_count=None,
                entitlements=self._entitlements.get(tenant_id),
                onboarding_completed_steps=(
                    onboarding.completed_steps if onboarding else ()
                ),
            )
            self._audit(
                "platform_tenant.viewed",
                actor_user_id=actor_user_id,
                target_tenant_id=tenant_id,
            )
            return summary

    async def list_platform_audit(
        self, *, limit: int
    ) -> tuple[PlatformAuditEvent, ...]:
        limit = validate_audit_limit(limit)
        async with self._lock:
            return tuple(reversed(self._platform_audit))[:limit]

    # Phase 13K support sessions ----------------------------------------------

    def _support_session(self, record: _SupportRecord, now: datetime) -> SupportSession:
        if record.ended_at is not None:
            state = "ended"
        elif now >= record.expires_at:
            state = "expired"
        else:
            state = "active"
        actor = self._users.get(record.actor_user_id)
        return SupportSession(
            session_id=record.session_id,
            actor_user_id=record.actor_user_id,
            actor_email=actor.email if actor else None,
            tenant_id=record.tenant_id,
            tenant_name=self._tenants.get(record.tenant_id, "Unknown tenant"),
            reason=record.reason,
            reference=record.reference,
            scopes=record.scopes,
            created_at=record.created_at,
            expires_at=record.expires_at,
            ended_at=record.ended_at,
            ended_by=record.ended_by,
            end_reason=record.end_reason,
            state=state,  # type: ignore[arg-type]
        )

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
        async with self._lock:
            if self._active_platform_role(actor_user_id) is None:
                raise PermissionError("Platform staff role is required.")
            if tenant_id not in self._tenants:
                raise WorkspaceNotFoundError("Workspace was not found.")
            now = self._now()
            for record in self._support.values():
                if (
                    record.actor_user_id == actor_user_id
                    and record.tenant_id == tenant_id
                    and record.ended_at is None
                    and now < record.expires_at
                ):
                    raise SupportSessionConflictError(
                        "You already have an active support session for this tenant."
                    )
            record = _SupportRecord(
                session_id=uuid4(),
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
                reason=normalized_reason,
                reference=normalized_reference,
                scopes=ordered,
                created_at=now,
                expires_at=now + timedelta(minutes=duration_minutes),
            )
            self._support[record.session_id] = record
            self._audit(
                "platform_support.session_started",
                actor_user_id=actor_user_id,
                target_tenant_id=tenant_id,
                reason=normalized_reason,
                support_session_id=record.session_id,
            )
            return self._support_session(record, now)

    async def get_support_session(
        self, session_id: UUID, *, now: datetime | None = None
    ) -> SupportSession:
        async with self._lock:
            record = self._support.get(session_id)
            if record is None:
                raise SupportSessionNotFoundError("Support session was not found.")
            return self._support_session(record, now or self._now())

    async def list_support_sessions(
        self, *, state: str, limit: int, now: datetime | None = None
    ) -> tuple[SupportSession, ...]:
        limit = validate_support_list(limit)
        if state not in ("active", "recent"):
            raise ValueError("state must be active or recent")
        async with self._lock:
            current = now or self._now()
            # Newest first; insertion order breaks ties from a coarse clock.
            ordered = [
                (record.created_at, index, self._support_session(record, current))
                for index, record in enumerate(self._support.values())
            ]
        ordered.sort(key=lambda item: (item[0], item[1]), reverse=True)
        sessions = [item[2] for item in ordered]
        if state == "active":
            sessions = [item for item in sessions if item.state == "active"]
        return tuple(sessions[:limit])

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
        async with self._lock:
            record = self._support.get(session_id)
            if record is None:
                raise SupportSessionNotFoundError("Support session was not found.")
            if self._active_platform_role(actor_user_id) is None:
                raise PermissionError("Platform staff role is required.")
            if record.actor_user_id != actor_user_id and not may_end_any:
                raise PermissionError("Only the session owner may end this session.")
            now = self._now()
            if record.ended_at is not None or now >= record.expires_at:
                raise SupportSessionClosedError("Support session is already closed.")
            record.ended_at = now
            record.ended_by = actor_user_id
            record.end_reason = normalized_reason
            self._audit(
                "platform_support.session_ended",
                actor_user_id=actor_user_id,
                target_tenant_id=record.tenant_id,
                reason=normalized_reason,
                support_session_id=session_id,
            )
            return self._support_session(record, now)

    async def authorize_support_read(
        self,
        *,
        actor_user_id: UUID,
        session_id: UUID,
        scope: SupportScope,
        now: datetime | None = None,
    ) -> SupportSession:
        async with self._lock:
            record = self._support.get(session_id)
            if record is None:
                raise SupportSessionNotFoundError("Support session was not found.")
            if (
                record.actor_user_id != actor_user_id
                or self._active_platform_role(actor_user_id) is None
            ):
                raise PermissionError("Only the session owner may read through it.")
            current = now or self._now()
            if record.ended_at is not None or current >= record.expires_at:
                raise SupportSessionClosedError("Support session is closed.")
            if scope not in record.scopes:
                raise PermissionError("This support session does not grant that scope.")
            self._audit(
                "platform_support.data_viewed",
                actor_user_id=actor_user_id,
                target_tenant_id=record.tenant_id,
                support_session_id=session_id,
                scope=scope,
            )
            return self._support_session(record, current)
