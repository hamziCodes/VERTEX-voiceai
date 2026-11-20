from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest

from control_plane.studio.models import (
    IdentityContext,
    OnboardingProfile,
    TenantEntitlements,
)
from control_plane.studio.repository import (
    InMemoryStudioRepository,
    InvitationConsumedError,
    InvitationExpiredError,
    LastAdminError,
)


def _identity(subject: str, email: str | None = None) -> IdentityContext:
    return IdentityContext(
        subject=subject,
        issuer="https://identity.test",
        email=email,
    )


def _token_hash(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_external_identity_is_unique_by_issuer_and_subject() -> None:
    repo = InMemoryStudioRepository()

    first = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    again = await repo.resolve_identity(_identity("owner", "new@example.com"))
    other = await repo.resolve_identity(_identity("other", "other@example.com"))

    assert again.user_id == first.user_id
    assert again.email == "new@example.com"
    assert other.user_id != first.user_id
    assert len(repo.safe_identity_snapshot()) == 2


@pytest.mark.asyncio
async def test_create_workspace_atomically_adds_owner() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))

    membership = await repo.create_workspace(owner.user_id, "Northwind Health")

    assert membership.role == "tenant_admin"
    assert membership.tenant_name == "Northwind Health"
    assert await repo.list_memberships(owner.user_id) == (membership,)
    onboarding = await repo.get_onboarding(membership.tenant_id)
    entitlements = await repo.get_entitlements(membership.tenant_id)
    assert onboarding.tenant_id == membership.tenant_id
    assert entitlements.tenant_id == membership.tenant_id


@pytest.mark.asyncio
async def test_invitation_token_is_hashed_single_use_and_expiring() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    member = await repo.resolve_identity(_identity("member", "member@example.com"))
    workspace = await repo.create_workspace(owner.user_id, "Northwind")
    now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    active_hash = _token_hash("active-invitation")

    invitation = await repo.create_invitation(
        workspace.tenant_id,
        email="member@example.com",
        role="tenant_editor",
        token_hash=active_hash,
        expires_at=now + timedelta(hours=1),
        invited_by=owner.user_id,
    )

    assert "token" not in invitation.model_dump()
    accepted = await repo.accept_invitation(active_hash, member.user_id, now=now)
    assert accepted.role == "tenant_editor"
    with pytest.raises(InvitationConsumedError):
        await repo.accept_invitation(active_hash, member.user_id, now=now)

    expired_hash = _token_hash("expired-invitation")
    await repo.create_invitation(
        workspace.tenant_id,
        email="late@example.com",
        role="tenant_viewer",
        token_hash=expired_hash,
        expires_at=now - timedelta(seconds=1),
        invited_by=owner.user_id,
    )
    with pytest.raises(InvitationExpiredError):
        await repo.accept_invitation(expired_hash, member.user_id, now=now)


@pytest.mark.asyncio
async def test_developer_is_a_supported_human_membership_role() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    developer = await repo.resolve_identity(
        _identity("developer", "developer@example.com")
    )
    workspace = await repo.create_workspace(owner.user_id, "Northwind")
    token_hash = _token_hash("developer-invitation")
    now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)

    await repo.create_invitation(
        workspace.tenant_id,
        email="developer@example.com",
        role="tenant_developer",
        token_hash=token_hash,
        expires_at=now + timedelta(hours=1),
        invited_by=owner.user_id,
    )
    membership = await repo.accept_invitation(token_hash, developer.user_id, now=now)

    assert membership.role == "tenant_developer"


@pytest.mark.asyncio
async def test_last_admin_cannot_be_removed_or_demoted() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    second = await repo.resolve_identity(_identity("second", "second@example.com"))
    workspace = await repo.create_workspace(owner.user_id, "Northwind")
    token_hash = _token_hash("second-admin")
    now = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    await repo.create_invitation(
        workspace.tenant_id,
        email="second@example.com",
        role="tenant_editor",
        token_hash=token_hash,
        expires_at=now + timedelta(hours=1),
        invited_by=owner.user_id,
    )
    await repo.accept_invitation(token_hash, second.user_id, now=now)

    with pytest.raises(LastAdminError):
        await repo.set_member_role(workspace.tenant_id, owner.user_id, "tenant_viewer")
    with pytest.raises(LastAdminError):
        await repo.remove_member(workspace.tenant_id, owner.user_id)

    await repo.set_member_role(workspace.tenant_id, second.user_id, "tenant_admin")
    updated = await repo.set_member_role(
        workspace.tenant_id, owner.user_id, "tenant_viewer"
    )
    assert updated.role == "tenant_viewer"


@pytest.mark.asyncio
async def test_onboarding_and_entitlements_are_tenant_scoped() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    alpha = await repo.create_workspace(owner.user_id, "Alpha")
    beta = await repo.create_workspace(owner.user_id, "Beta")

    alpha_profile = await repo.save_onboarding(
        OnboardingProfile(
            tenant_id=alpha.tenant_id,
            business_name="Alpha Clinic",
            use_case="appointment_intake",
            languages=("en", "ur"),
            timezone="Asia/Karachi",
            completed_steps=("business", "language"),
        )
    )
    alpha_entitlements = await repo.save_entitlements(
        TenantEntitlements(
            tenant_id=alpha.tenant_id,
            max_agents=4,
            telephony_enabled=True,
        )
    )

    assert (await repo.get_onboarding(alpha.tenant_id)) == alpha_profile
    assert (await repo.get_onboarding(beta.tenant_id)).business_name == ""
    assert (await repo.get_entitlements(alpha.tenant_id)) == alpha_entitlements
    assert (await repo.get_entitlements(beta.tenant_id)).max_agents == 1
    assert (await repo.get_entitlements(beta.tenant_id)).telephony_enabled is False


@pytest.mark.asyncio
async def test_repository_does_not_return_secret_material() -> None:
    repo = InMemoryStudioRepository()
    owner = await repo.resolve_identity(_identity("owner", "owner@example.com"))
    workspace = await repo.create_workspace(owner.user_id, "Northwind")
    token_hash = _token_hash("never-return-this")

    invitation = await repo.create_invitation(
        workspace.tenant_id,
        email="member@example.com",
        role="tenant_viewer",
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        invited_by=owner.user_id,
    )

    serialized = repr(invitation) + repr(repo.safe_identity_snapshot())
    assert token_hash not in serialized
    assert "password_hash" not in serialized
    assert "access_token" not in serialized
