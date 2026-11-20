"""Phase 13H disposable PostgreSQL proof for migration 031 (five launch roles)."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)

MIGRATION_031 = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "031_studio_customer_roles.sql"
)
LAUNCH_ROLES = (
    "tenant_admin",
    "tenant_editor",
    "tenant_developer",
    "tenant_viewer",
    "compliance_admin",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase13h_migration_031_roles_constraints_rls_and_last_admin() -> None:
    import psycopg
    from psycopg import errors

    from control_plane.studio.models import IdentityContext
    from control_plane.studio.pg_repository import PostgresStudioRepository
    from control_plane.studio.repository import LastAdminError
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"

    await apply_migrations_async(database_url)
    # Bookkeeping makes a second run a no-op.
    assert await apply_migrations_async(database_url) == []

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=2)
    await database.open()
    fixture = await psycopg.AsyncConnection.connect(database_url)
    try:
        recorded = await (
            await fixture.execute(
                "SELECT checksum_sha256 IS NOT NULL FROM schema_migrations "
                "WHERE filename = %s",
                ("031_studio_customer_roles.sql",),
            )
        ).fetchone()
        assert recorded == (True,)
        constraints = await (
            await fixture.execute(
                """
                SELECT conname, convalidated, pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conname IN (
                    'memberships_role_check', 'workspace_invitations_role_check'
                )
                ORDER BY conname
                """
            )
        ).fetchall()
        assert [row[0] for row in constraints] == [
            "memberships_role_check",
            "workspace_invitations_role_check",
        ]
        for _, validated, definition in constraints:
            assert validated is True
            for role in LAUNCH_ROLES:
                assert f"'{role}'" in definition
            assert "platform_admin" not in definition

        studio = PostgresStudioRepository(database)
        owner = await studio.resolve_identity(
            IdentityContext(
                issuer="https://phase13h.test",
                subject="owner",
                email="owner@phase13h.test",
            )
        )
        developer = await studio.resolve_identity(
            IdentityContext(
                issuer="https://phase13h.test", subject="dev", email="dev@phase13h.test"
            )
        )
        outsider = await studio.resolve_identity(
            IdentityContext(
                issuer="https://phase13h.test",
                subject="other",
                email="other@phase13h.test",
            )
        )
        workspace = await studio.create_workspace(owner.user_id, "Phase 13H A")
        other_workspace = await studio.create_workspace(outsider.user_id, "Phase 13H B")

        token_hash = "b" * 64
        await studio.create_invitation(
            workspace.tenant_id,
            email="dev@phase13h.test",
            role="tenant_developer",
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            invited_by=owner.user_id,
        )
        accepted = await studio.accept_invitation(token_hash, developer.user_id)
        assert accepted.role == "tenant_developer"
        listed = {
            item.user_id: item.role
            for item in await studio.list_workspace_members(workspace.tenant_id)
        }
        assert listed == {
            owner.user_id: "tenant_admin",
            developer.user_id: "tenant_developer",
        }

        # Last-administrator protection holds in the durable repository.
        with pytest.raises(LastAdminError):
            await studio.set_member_role(
                workspace.tenant_id, owner.user_id, "tenant_viewer"
            )
        with pytest.raises(LastAdminError):
            await studio.remove_member(workspace.tenant_id, owner.user_id)
        await studio.set_member_role(
            workspace.tenant_id, developer.user_id, "tenant_admin"
        )
        demoted = await studio.set_member_role(
            workspace.tenant_id, owner.user_id, "tenant_editor"
        )
        assert demoted.role == "tenant_editor"

        # Roles outside the five launch roles are rejected by both constraints.
        for invalid_role in ("tenant_owner", "platform_admin", "superadmin"):
            with pytest.raises(errors.CheckViolation):
                async with fixture.transaction():
                    await fixture.execute(
                        "INSERT INTO memberships (user_id, tenant_id, role) "
                        "VALUES (%s, %s, %s)",
                        (outsider.user_id, workspace.tenant_id, invalid_role),
                    )
            with pytest.raises(errors.CheckViolation):
                async with fixture.transaction():
                    await fixture.execute(
                        """
                        INSERT INTO workspace_invitations
                            (tenant_id, email, role, token_hash, invited_by, expires_at)
                        VALUES (%s, %s, %s, %s, %s, NOW() + INTERVAL '1 hour')
                        """,
                        (
                            workspace.tenant_id,
                            "x@phase13h.test",
                            invalid_role,
                            "c" * 64,
                            owner.user_id,
                        ),
                    )

        # Re-running 031 over existing valid rows is safe; both constraints stay
        # validated.
        async with fixture.transaction():
            await fixture.execute(MIGRATION_031.read_text(encoding="utf-8"))
        revalidated = await (
            await fixture.execute(
                "SELECT bool_and(convalidated), count(*) FROM pg_constraint "
                "WHERE conname IN "
                "('memberships_role_check', 'workspace_invitations_role_check')"
            )
        ).fetchone()
        assert revalidated == (True, 2)

        # RLS: the application role sees only the tenant set in app.tenant_id.
        async with fixture.transaction():
            await fixture.execute("SET LOCAL ROLE ucve_app")
            await fixture.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (str(other_workspace.tenant_id),),
            )
            leaked = await (
                await fixture.execute(
                    "SELECT COUNT(*) FROM memberships WHERE tenant_id = %s",
                    (workspace.tenant_id,),
                )
            ).fetchone()
            leaked_invitations = await (
                await fixture.execute(
                    "SELECT COUNT(*) FROM workspace_invitations WHERE tenant_id = %s",
                    (workspace.tenant_id,),
                )
            ).fetchone()
            own = await (
                await fixture.execute("SELECT COUNT(*) FROM memberships")
            ).fetchone()
        assert leaked == (0,)
        assert leaked_invitations == (0,)
        assert own == (1,)
    finally:
        await fixture.close()
        await database.close()
