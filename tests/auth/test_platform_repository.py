"""Phase 13J: platform staff repository contract (in-memory implementation)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from control_plane.studio.models import IdentityContext
from control_plane.studio.repository import (
    InMemoryStudioRepository,
    LastPlatformAdminError,
    StaffNotFoundError,
    WorkspaceNotFoundError,
)

REASON = "Support rota for Q4 onboarding"


def _run(coro):
    return asyncio.run(coro)


async def _user(repo: InMemoryStudioRepository, name: str):
    return await repo.resolve_identity(
        IdentityContext(
            subject=f"sub-{name}", issuer="https://id.test", email=f"{name}@wavia.test"
        )
    )


async def _with_admin():
    repo = InMemoryStudioRepository()
    admin = await _user(repo, "admin")
    await repo.bootstrap_platform_admin(
        admin.user_id, reason="Initial operator bootstrap"
    )
    return repo, admin


def test_bootstrap_and_role_lookup() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        other = await _user(repo, "customer")
        assert await repo.get_platform_role(admin.user_id) == "platform_admin"
        assert await repo.get_platform_role(other.user_id) is None

    _run(scenario())


def test_grant_requires_reason_existing_user_and_admin_actor() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        support = await _user(repo, "support")
        with pytest.raises(ValueError):
            await repo.grant_platform_role(
                actor_user_id=admin.user_id,
                email="support@wavia.test",
                role="platform_support",
                reason="short",
            )
        with pytest.raises(StaffNotFoundError):
            await repo.grant_platform_role(
                actor_user_id=admin.user_id,
                email="nobody@wavia.test",
                role="platform_support",
                reason=REASON,
            )
        with pytest.raises(ValueError):
            await repo.grant_platform_role(
                actor_user_id=admin.user_id,
                email="support@wavia.test",
                role="tenant_admin",  # type: ignore[arg-type]
                reason=REASON,
            )
        with pytest.raises(PermissionError):
            await repo.grant_platform_role(
                actor_user_id=support.user_id,
                email="support@wavia.test",
                role="platform_admin",
                reason=REASON,
            )
        member = await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email=" Support@Wavia.test ",
            role="platform_support",
            reason=REASON,
        )
        assert member.user_id == support.user_id
        assert member.role == "platform_support"
        assert member.granted_by == admin.user_id
        assert await repo.get_platform_role(support.user_id) == "platform_support"
        # Support staff cannot grant.
        with pytest.raises(PermissionError):
            await repo.grant_platform_role(
                actor_user_id=support.user_id,
                email="support@wavia.test",
                role="platform_admin",
                reason=REASON,
            )

    _run(scenario())


def test_role_change_and_revoke_are_audited_once_each() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        support = await _user(repo, "support")
        await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email="support@wavia.test",
            role="platform_support",
            reason=REASON,
        )
        # Same role again is a no-op, not a second event.
        await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email="support@wavia.test",
            role="platform_support",
            reason=REASON,
        )
        await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email="support@wavia.test",
            role="platform_admin",
            reason="Promoted to platform administration",
        )
        with pytest.raises(ValueError):
            await repo.revoke_platform_role(
                actor_user_id=admin.user_id, user_id=support.user_id, reason="no"
            )
        await repo.revoke_platform_role(
            actor_user_id=admin.user_id,
            user_id=support.user_id,
            reason="Left the support rota",
        )
        assert await repo.get_platform_role(support.user_id) is None
        with pytest.raises(StaffNotFoundError):
            await repo.revoke_platform_role(
                actor_user_id=admin.user_id,
                user_id=support.user_id,
                reason="Left the support rota",
            )
        events = await repo.list_platform_audit(limit=50)
        actions = [event.action for event in events]
        assert actions == [
            "platform_staff.revoked",
            "platform_staff.role_changed",
            "platform_staff.granted",
        ]
        changed = events[1]
        assert changed.previous_role == "platform_support"
        assert changed.new_role == "platform_admin"
        assert changed.actor_user_id == admin.user_id
        assert changed.target_user_id == support.user_id
        assert events[0].reason == "Left the support rota"
        staff = await repo.list_platform_staff()
        assert [member.user_id for member in staff] == [admin.user_id]

    _run(scenario())


def test_last_platform_admin_cannot_be_revoked_or_demoted() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        with pytest.raises(LastPlatformAdminError):
            await repo.revoke_platform_role(
                actor_user_id=admin.user_id, user_id=admin.user_id, reason=REASON
            )
        with pytest.raises(LastPlatformAdminError):
            await repo.grant_platform_role(
                actor_user_id=admin.user_id,
                email="admin@wavia.test",
                role="platform_support",
                reason=REASON,
            )
        second = await _user(repo, "second")
        await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email="second@wavia.test",
            role="platform_admin",
            reason=REASON,
        )
        await repo.revoke_platform_role(
            actor_user_id=second.user_id, user_id=admin.user_id, reason=REASON
        )
        assert await repo.get_platform_role(admin.user_id) is None
        assert await repo.get_platform_role(second.user_id) == "platform_admin"

    _run(scenario())


def test_tenant_directory_is_bounded_and_searchable() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        owner = await _user(repo, "owner")
        names = ["Acme Dental", "Beacon Clinic", "acme logistics", "Zephyr 100%"]
        created = {}
        for name in names:
            membership = await repo.create_workspace(owner.user_id, name)
            created[name] = membership.tenant_id

        page = await repo.list_tenant_directory(query=None, limit=2, offset=0)
        assert page.total == 4
        assert [item.name for item in page.items] == ["Acme Dental", "acme logistics"]
        assert page.items[0].member_count == 1
        assert page.items[0].agent_count is None  # not tracked in memory
        second = await repo.list_tenant_directory(query=None, limit=2, offset=2)
        assert [item.name for item in second.items] == ["Beacon Clinic", "Zephyr 100%"]

        search = await repo.list_tenant_directory(query="ACME", limit=25, offset=0)
        assert {item.name for item in search.items} == {"Acme Dental", "acme logistics"}
        literal = await repo.list_tenant_directory(query="100%", limit=25, offset=0)
        assert [item.name for item in literal.items] == ["Zephyr 100%"]
        by_id = await repo.list_tenant_directory(
            query=str(created["Beacon Clinic"]), limit=25, offset=0
        )
        assert [item.name for item in by_id.items] == ["Beacon Clinic"]

        for limit, offset in ((0, 0), (51, 0), (10, -1), (10, 10_001)):
            with pytest.raises(ValueError):
                await repo.list_tenant_directory(query=None, limit=limit, offset=offset)
        with pytest.raises(ValueError):
            await repo.list_tenant_directory(query="x" * 256, limit=10, offset=0)

    _run(scenario())


def test_tenant_summary_is_safe_and_audited() -> None:
    async def scenario() -> None:
        repo, admin = await _with_admin()
        owner = await _user(repo, "owner")
        workspace = await repo.create_workspace(owner.user_id, "Acme Dental")
        customer = await _user(repo, "customer")

        with pytest.raises(PermissionError):
            await repo.view_tenant_summary(
                workspace.tenant_id, actor_user_id=customer.user_id
            )
        with pytest.raises(WorkspaceNotFoundError):
            await repo.view_tenant_summary(uuid4(), actor_user_id=admin.user_id)

        summary = await repo.view_tenant_summary(
            workspace.tenant_id, actor_user_id=admin.user_id
        )
        assert summary.name == "Acme Dental"
        assert summary.members_by_role == {"tenant_admin": 1}
        assert summary.entitlements is not None
        assert summary.onboarding_completed_steps == ()
        dumped = summary.model_dump(mode="json")
        assert "email" not in str(dumped)
        assert "token" not in str(dumped)

        events = await repo.list_platform_audit(limit=10)
        assert events[0].action == "platform_tenant.viewed"
        assert events[0].target_tenant_id == workspace.tenant_id
        assert events[0].actor_user_id == admin.user_id

    _run(scenario())


def test_platform_audit_limit_is_bounded() -> None:
    async def scenario() -> None:
        repo, _ = await _with_admin()
        for limit in (0, 101):
            with pytest.raises(ValueError):
                await repo.list_platform_audit(limit=limit)

    _run(scenario())
