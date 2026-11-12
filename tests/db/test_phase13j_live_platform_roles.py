"""Phase 13J disposable PostgreSQL proof for migration 032 (platform staff)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)

MIGRATION_032 = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "032_platform_staff_roles.sql"
)
REASON = "Phase 13J disposable database proof"


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase13j_migration_032_staff_roles_audit_and_isolation() -> None:
    import psycopg
    from psycopg import errors

    from control_plane.studio.models import IdentityContext
    from control_plane.studio.pg_repository import PostgresStudioRepository
    from control_plane.studio.repository import (
        LastPlatformAdminError,
        StaffNotFoundError,
    )
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"

    await apply_migrations_async(database_url)
    assert await apply_migrations_async(database_url) == []

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=4)
    await database.open()
    fixture = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    try:
        recorded = await (
            await fixture.execute(
                "SELECT checksum_sha256 IS NOT NULL FROM schema_migrations "
                "WHERE filename = %s",
                ("032_platform_staff_roles.sql",),
            )
        ).fetchone()
        assert recorded == (True,)

        studio = PostgresStudioRepository(database)

        async def user(name: str):
            return await studio.resolve_identity(
                IdentityContext(
                    issuer="https://phase13j.test",
                    subject=name,
                    email=f"{name}@phase13j.test",
                )
            )

        legacy = await user("legacy")
        second = await user("second")
        support = await user("support")
        owner = await user("owner")

        # Backfill: a flagged legacy user becomes a durable platform admin with
        # exactly one migration audit event, even when 032 runs again.
        await fixture.execute(
            "UPDATE users SET is_platform_admin = TRUE WHERE id = %s",
            (legacy.user_id,),
        )
        for _ in range(2):
            async with fixture.transaction():
                await fixture.execute(MIGRATION_032.read_text(encoding="utf-8"))
        assert await studio.get_platform_role(legacy.user_id) == "platform_admin"
        migrated = await (
            await fixture.execute(
                "SELECT COUNT(*) FROM platform_audit_events "
                "WHERE action = 'platform_staff.migrated' AND target_user_id = %s",
                (legacy.user_id,),
            )
        ).fetchone()
        assert migrated == (1,)

        # Grants, role changes and revocations are reasoned and audited.
        granted = await studio.grant_platform_role(
            actor_user_id=legacy.user_id,
            email="support@phase13j.test",
            role="platform_support",
            reason=REASON,
        )
        assert granted.role == "platform_support"
        assert granted.granted_by == legacy.user_id
        with pytest.raises(PermissionError):
            await studio.grant_platform_role(
                actor_user_id=support.user_id,
                email="owner@phase13j.test",
                role="platform_admin",
                reason=REASON,
            )
        with pytest.raises(StaffNotFoundError):
            await studio.grant_platform_role(
                actor_user_id=legacy.user_id,
                email="missing@phase13j.test",
                role="platform_support",
                reason=REASON,
            )
        with pytest.raises(LastPlatformAdminError):
            await studio.revoke_platform_role(
                actor_user_id=legacy.user_id, user_id=legacy.user_id, reason=REASON
            )
        await studio.grant_platform_role(
            actor_user_id=legacy.user_id,
            email="second@phase13j.test",
            role="platform_admin",
            reason=REASON,
        )
        staff = {item.user_id: item.role for item in await studio.list_platform_staff()}
        assert staff == {
            legacy.user_id: "platform_admin",
            second.user_id: "platform_admin",
            support.user_id: "platform_support",
        }

        # Concurrent mutual revocation leaves exactly one platform admin.
        outcomes = await asyncio.gather(
            studio.revoke_platform_role(
                actor_user_id=legacy.user_id, user_id=second.user_id, reason=REASON
            ),
            studio.revoke_platform_role(
                actor_user_id=second.user_id, user_id=legacy.user_id, reason=REASON
            ),
            return_exceptions=True,
        )
        failures = [item for item in outcomes if isinstance(item, BaseException)]
        assert len(failures) == 1
        assert isinstance(failures[0], (LastPlatformAdminError, PermissionError))
        active_admins = await (
            await fixture.execute(
                "SELECT COUNT(*) FROM platform_memberships "
                "WHERE role = 'platform_admin' AND revoked_at IS NULL"
            )
        ).fetchone()
        assert active_admins == (1,)
        remaining_admin = next(
            item.user_id
            for item in await studio.list_platform_staff()
            if item.role == "platform_admin"
        )

        # Directory and summary read across tenants and audit the detail view.
        workspace = await studio.create_workspace(owner.user_id, "Phase 13J Clinic")
        page = await studio.list_tenant_directory(query="phase 13j", limit=10, offset=0)
        assert [item.tenant_id for item in page.items] == [workspace.tenant_id]
        assert page.items[0].member_count == 1
        assert page.items[0].agent_count == 0
        summary = await studio.view_tenant_summary(
            workspace.tenant_id, actor_user_id=support.user_id
        )
        assert summary.members_by_role == {"tenant_admin": 1}
        assert summary.agent_count == 0
        events = await studio.list_platform_audit(limit=5)
        assert events[0].action == "platform_tenant.viewed"
        assert events[0].actor_user_id == support.user_id
        with pytest.raises(PermissionError):
            await studio.view_tenant_summary(
                workspace.tenant_id, actor_user_id=owner.user_id
            )

        # Constraints: unknown roles and missing reasons are rejected.
        for role, reason in (("superadmin", REASON), ("platform_support", "short")):
            with pytest.raises(errors.CheckViolation):
                async with fixture.transaction():
                    await fixture.execute(
                        "INSERT INTO platform_memberships (user_id, role, reason) "
                        "VALUES (%s, %s, %s)",
                        (owner.user_id, role, reason),
                    )

        # Platform audit is append-only.
        with pytest.raises(errors.RaiseException):
            async with fixture.transaction():
                await fixture.execute(
                    "UPDATE platform_audit_events SET reason = 'tampered'"
                )
        with pytest.raises(errors.RaiseException):
            async with fixture.transaction():
                await fixture.execute("DELETE FROM platform_audit_events")

        # The tenant application role cannot see platform tables at all.
        for table in ("platform_memberships", "platform_audit_events"):
            with pytest.raises(errors.InsufficientPrivilege):
                async with fixture.transaction():
                    await fixture.execute("SET LOCAL ROLE ucve_app")
                    await fixture.execute(f"SELECT COUNT(*) FROM {table}")

        assert remaining_admin in {legacy.user_id, second.user_id}
    finally:
        await fixture.close()
        await database.close()
