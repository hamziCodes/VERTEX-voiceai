"""Safe domain models for Studio identity, workspaces, and onboarding."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

StudioRole = Literal[
    "tenant_admin",
    "tenant_editor",
    "tenant_developer",
    "tenant_viewer",
    "compliance_admin",
]


class StudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IdentityContext(StudioModel):
    subject: str = Field(min_length=1, max_length=512)
    issuer: str = Field(min_length=1, max_length=1024)
    email: str | None = Field(default=None, max_length=320)

    @field_validator("subject", "issuer")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None


class UserIdentity(StudioModel):
    user_id: UUID
    issuer: str
    subject: str
    email: str | None = None
    is_active: bool = True
    is_platform_admin: bool = False


class WorkspaceMembership(StudioModel):
    user_id: UUID
    tenant_id: UUID
    tenant_name: str = Field(min_length=1, max_length=255)
    role: StudioRole
    created_at: datetime


class WorkspaceInvitation(StudioModel):
    invitation_id: UUID
    tenant_id: UUID
    email: str = Field(min_length=3, max_length=320)
    role: StudioRole
    invited_by: UUID
    expires_at: datetime
    accepted_at: datetime | None = None
    accepted_by: UUID | None = None
    created_at: datetime

    @field_validator("email")
    @classmethod
    def normalize_invitation_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not normalized:
            raise ValueError("email must not be blank")
        return normalized


class OnboardingProfile(StudioModel):
    tenant_id: UUID
    business_name: str = Field(default="", max_length=255)
    use_case: str = Field(default="", max_length=64)
    languages: tuple[str, ...] = ("en",)
    operating_region: str = Field(default="", max_length=128)
    timezone: str = Field(default="UTC", min_length=1, max_length=128)
    escalation_email: str | None = Field(default=None, max_length=320)
    completed_steps: tuple[str, ...] = ()
    updated_at: datetime | None = None

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(
            dict.fromkeys(value.strip().lower() for value in values if value.strip())
        )
        if not normalized:
            raise ValueError("at least one language is required")
        return normalized

    @field_validator("escalation_email")
    @classmethod
    def normalize_escalation_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None


class TenantEntitlements(StudioModel):
    tenant_id: UUID
    max_agents: int = Field(default=1, ge=1, le=10_000)
    max_concurrent_sessions: int = Field(default=1, ge=1, le=10_000)
    max_knowledge_bytes: int = Field(default=10_485_760, ge=0)
    api_keys_allowed: int = Field(default=2, ge=0, le=10_000)
    telephony_enabled: bool = False
    advanced_providers_enabled: bool = False
    byok_enabled: bool = False
    allowed_retention_days: tuple[int, ...] = (7, 30)
    updated_at: datetime | None = None

    @field_validator("allowed_retention_days")
    @classmethod
    def validate_retention_days(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        normalized = tuple(sorted(set(values)))
        if any(value < 1 or value > 3650 for value in normalized):
            raise ValueError("retention days must be between 1 and 3650")
        return normalized


PlatformRole = Literal["platform_admin", "platform_support"]

PlatformAuditAction = Literal[
    "platform_staff.migrated",
    "platform_staff.granted",
    "platform_staff.role_changed",
    "platform_staff.revoked",
    "platform_tenant.viewed",
    "platform_support.session_started",
    "platform_support.session_ended",
    "platform_support.data_viewed",
]

SupportScope = Literal["configuration", "readiness"]
SUPPORT_SCOPES: tuple[SupportScope, ...] = ("configuration", "readiness")
SupportSessionState = Literal["active", "expired", "ended"]


class PlatformStaffMember(StudioModel):
    """An active Wavia staff assignment. Safe for internal responses."""

    user_id: UUID
    email: str | None = None
    role: PlatformRole
    granted_by: UUID | None = None
    granted_at: datetime
    reason: str


class PlatformAuditEvent(StudioModel):
    event_id: UUID
    actor_user_id: UUID | None = None
    action: PlatformAuditAction
    target_user_id: UUID | None = None
    target_tenant_id: UUID | None = None
    previous_role: PlatformRole | None = None
    new_role: PlatformRole | None = None
    reason: str | None = None
    support_session_id: UUID | None = None
    scope: SupportScope | None = None
    created_at: datetime


class TenantDirectoryEntry(StudioModel):
    tenant_id: UUID
    name: str
    created_at: datetime
    member_count: int = Field(ge=0)
    agent_count: int | None = Field(default=None, ge=0)


class TenantDirectoryPage(StudioModel):
    items: tuple[TenantDirectoryEntry, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50)
    offset: int = Field(ge=0, le=10_000)


class TenantSummary(StudioModel):
    """Safe tenant metadata for staff: counts and configuration, no customer data."""

    tenant_id: UUID
    name: str
    created_at: datetime
    members_by_role: dict[StudioRole, int]
    agent_count: int | None = Field(default=None, ge=0)
    entitlements: TenantEntitlements | None = None
    onboarding_completed_steps: tuple[str, ...] = ()


class SupportSession(StudioModel):
    """A read-only, expiring support grant. ``state`` is evaluated at read time."""

    session_id: UUID
    actor_user_id: UUID
    actor_email: str | None = None
    tenant_id: UUID
    tenant_name: str
    reason: str
    reference: str | None = None
    scopes: tuple[SupportScope, ...]
    created_at: datetime
    expires_at: datetime
    ended_at: datetime | None = None
    ended_by: UUID | None = None
    end_reason: str | None = None
    state: SupportSessionState
