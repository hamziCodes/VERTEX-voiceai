"""Phase 13K: read-only, expiring, audited support sessions (repository contract)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from control_plane.auth.platform_rbac import platform_permissions_for_role
from control_plane.studio.models import IdentityContext
from control_plane.studio.repository import (
    InMemoryStudioRepository,
    SupportSessionClosedError,
    SupportSessionConflictError,
    SupportSessionNotFoundError,
    WorkspaceNotFoundError,
)

REASON = "Customer ticket about agent setup"


def _run(coro):
    return asyncio.run(coro)


async def _user(repo: InMemoryStudioRepository, name: str):
    return await repo.resolve_identity(
        IdentityContext(
            subject=f"sub-{name}", issuer="https://id.test", email=f"{name}@wavia.test"
        )
    )


async def _setup():
    repo = InMemoryStudioRepository()
    admin = await _user(repo, "admin")
    support = await _user(repo, "support")
    other = await _user(repo, "other")
    owner = await _user(repo, "owner")
    await repo.bootstrap_platform_admin(
        admin.user_id, reason="Initial operator bootstrap"
    )
    for member in ("support", "other"):
        await repo.grant_platform_role(
            actor_user_id=admin.user_id,
            email=f"{member}@wavia.test",
            role="platform_support",
            reason="Support rota for launch",
        )
    workspace = await repo.create_workspace(owner.user_id, "Acme Dental")
    return repo, admin, support, other, owner, workspace.tenant_id


def test_support_session_permissions_are_explicit() -> None:
    admin = platform_permissions_for_role("platform_admin")
    support = platform_permissions_for_role("platform_support")
    assert {
        "platform_support_session:read",
        "platform_support_session:write",
        "platform_support_session:manage",
        "platform_operations:read",
    } <= admin
    assert {
        "platform_support_session:read",
        "platform_support_session:write",
    } <= support
    assert "platform_support_session:manage" not in support
    assert "platform_operations:read" not in support
    for permissions in (admin, support):
        assert not any(item.endswith(":*") or item == "*" for item in permissions)


def test_start_validates_actor_tenant_reason_scopes_and_duration() -> None:
    async def scenario() -> None:
        repo, _, support, _, owner, tenant = await _setup()

        async def start(**overrides):
            values = {
                "actor_user_id": support.user_id,
                "tenant_id": tenant,
                "reason": REASON,
                "reference": "TICKET-1042",
                "scopes": ("configuration",),
                "duration_minutes": 30,
            }
            values.update(overrides)
            return await repo.start_support_session(**values)

        with pytest.raises(PermissionError):
            await start(actor_user_id=owner.user_id)
        with pytest.raises(WorkspaceNotFoundError):
            await start(tenant_id=uuid4())
        with pytest.raises(ValueError):
            await start(reason="short")
        with pytest.raises(ValueError):
            await start(scopes=())
        with pytest.raises(ValueError):
            await start(scopes=("transcripts",))
        with pytest.raises(ValueError):
            await start(duration_minutes=90)
        with pytest.raises(ValueError):
            await start(reference="x" * 65)

        session = await start(scopes=("readiness", "configuration", "readiness"))
        assert session.state == "active"
        assert session.scopes == ("configuration", "readiness")
        assert session.tenant_name == "Acme Dental"
        assert session.actor_email == "support@wavia.test"
        assert session.expires_at - session.created_at == timedelta(minutes=30)
        assert session.reference == "TICKET-1042"

        with pytest.raises(SupportSessionConflictError):
            await start()

        events = await repo.list_platform_audit(limit=5)
        assert events[0].action == "platform_support.session_started"
        assert events[0].support_session_id == session.session_id
        assert events[0].target_tenant_id == tenant
        assert events[0].reason == REASON

    _run(scenario())


def test_reads_require_owner_active_session_and_granted_scope() -> None:
    async def scenario() -> None:
        repo, admin, support, other, _, tenant = await _setup()
        session = await repo.start_support_session(
            actor_user_id=support.user_id,
            tenant_id=tenant,
            reason=REASON,
            reference=None,
            scopes=("configuration",),
            duration_minutes=15,
        )

        granted = await repo.authorize_support_read(
            actor_user_id=support.user_id,
            session_id=session.session_id,
            scope="configuration",
        )
        assert granted.tenant_id == tenant
        for actor in (other.user_id, admin.user_id):
            with pytest.raises(PermissionError):
                await repo.authorize_support_read(
                    actor_user_id=actor,
                    session_id=session.session_id,
                    scope="configuration",
                )
        with pytest.raises(PermissionError):
            await repo.authorize_support_read(
                actor_user_id=support.user_id,
                session_id=session.session_id,
                scope="readiness",
            )
        with pytest.raises(SupportSessionNotFoundError):
            await repo.authorize_support_read(
                actor_user_id=support.user_id, session_id=uuid4(), scope="configuration"
            )
        later = datetime.now(UTC) + timedelta(minutes=16)
        with pytest.raises(SupportSessionClosedError):
            await repo.authorize_support_read(
                actor_user_id=support.user_id,
                session_id=session.session_id,
                scope="configuration",
                now=later,
            )
        expired = await repo.get_support_session(session.session_id, now=later)
        assert expired.state == "expired"

        viewed = [
            event
            for event in await repo.list_platform_audit(limit=20)
            if event.action == "platform_support.data_viewed"
        ]
        assert len(viewed) == 1
        assert viewed[0].scope == "configuration"
        assert viewed[0].actor_user_id == support.user_id
        assert viewed[0].support_session_id == session.session_id

    _run(scenario())


def test_ending_respects_ownership_and_management() -> None:
    async def scenario() -> None:
        repo, admin, support, other, _, tenant = await _setup()

        async def open_for(actor):
            return await repo.start_support_session(
                actor_user_id=actor.user_id,
                tenant_id=tenant,
                reason=REASON,
                reference=None,
                scopes=("readiness",),
                duration_minutes=60,
            )

        first = await open_for(support)
        with pytest.raises(PermissionError):
            await repo.end_support_session(
                actor_user_id=other.user_id,
                session_id=first.session_id,
                reason=None,
                may_end_any=False,
            )
        with pytest.raises(ValueError):
            await repo.end_support_session(
                actor_user_id=support.user_id,
                session_id=first.session_id,
                reason="short",
                may_end_any=False,
            )
        ended = await repo.end_support_session(
            actor_user_id=support.user_id,
            session_id=first.session_id,
            reason=None,
            may_end_any=False,
        )
        assert ended.state == "ended"
        assert ended.ended_by == support.user_id
        with pytest.raises(SupportSessionClosedError):
            await repo.end_support_session(
                actor_user_id=support.user_id,
                session_id=first.session_id,
                reason=None,
                may_end_any=False,
            )
        with pytest.raises(SupportSessionClosedError):
            await repo.authorize_support_read(
                actor_user_id=support.user_id,
                session_id=first.session_id,
                scope="readiness",
            )

        # A new session is allowed once the previous one ended; an admin may end it.
        second = await open_for(support)
        closed = await repo.end_support_session(
            actor_user_id=admin.user_id,
            session_id=second.session_id,
            reason="Ending stale session after handover",
            may_end_any=True,
        )
        assert closed.end_reason == "Ending stale session after handover"

        active = await repo.list_support_sessions(state="active", limit=10)
        recent = await repo.list_support_sessions(state="recent", limit=10)
        assert active == ()
        assert [item.session_id for item in recent] == [
            second.session_id,
            first.session_id,
        ]
        for limit in (0, 101):
            with pytest.raises(ValueError):
                await repo.list_support_sessions(state="recent", limit=limit)

        ends = [
            event.action
            for event in await repo.list_platform_audit(limit=20)
            if event.action == "platform_support.session_ended"
        ]
        assert len(ends) == 2

    _run(scenario())


def test_revoked_staff_cannot_use_an_open_session() -> None:
    async def scenario() -> None:
        repo, admin, support, _, _, tenant = await _setup()
        session = await repo.start_support_session(
            actor_user_id=support.user_id,
            tenant_id=tenant,
            reason=REASON,
            reference=None,
            scopes=("configuration",),
            duration_minutes=15,
        )
        await repo.revoke_platform_role(
            actor_user_id=admin.user_id,
            user_id=support.user_id,
            reason="Left the support rota",
        )
        with pytest.raises(PermissionError):
            await repo.authorize_support_read(
                actor_user_id=support.user_id,
                session_id=session.session_id,
                scope="configuration",
            )

    _run(scenario())
