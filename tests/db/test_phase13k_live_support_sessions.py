"""Phase 13K disposable PostgreSQL proof for migration 033 (support sessions)."""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)
REASON = "Phase 13K disposable database proof"


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase13k_migration_033_support_sessions() -> None:
    import psycopg
    from psycopg import errors

    from control_plane.studio.models import IdentityContext
    from control_plane.studio.pg_repository import PostgresStudioRepository
    from control_plane.studio.repository import (
        SupportSessionClosedError,
        SupportSessionConflictError,
    )
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    assert await apply_migrations_async(database_url) == []

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=3)
    await database.open()
    fixture = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    try:
        recorded = await (
            await fixture.execute(
                "SELECT checksum_sha256 IS NOT NULL FROM schema_migrations "
                "WHERE filename = %s",
                ("033_platform_support_sessions.sql",),
            )
        ).fetchone()
        assert recorded == (True,)

        studio = PostgresStudioRepository(database)

        async def user(name: str):
            return await studio.resolve_identity(
                IdentityContext(
                    issuer="https://phase13k.test",
                    subject=name,
                    email=f"{name}@phase13k.test",
                )
            )

        admin = await user("admin")
        support = await user("support")
        owner = await user("owner")
        await fixture.execute(
            "INSERT INTO platform_memberships (user_id, role, reason) "
            "VALUES (%s, 'platform_admin', %s) ON CONFLICT (user_id) DO NOTHING",
            (admin.user_id, REASON),
        )
        await studio.grant_platform_role(
            actor_user_id=admin.user_id,
            email="support@phase13k.test",
            role="platform_support",
            reason=REASON,
        )
        workspace = await studio.create_workspace(owner.user_id, "Phase 13K Clinic")

        session = await studio.start_support_session(
            actor_user_id=support.user_id,
            tenant_id=workspace.tenant_id,
            reason=REASON,
            reference="TICKET-13K",
            scopes=("readiness",),
            duration_minutes=15,
        )
        assert session.state == "active"
        assert session.tenant_name == "Phase 13K Clinic"
        with pytest.raises(SupportSessionConflictError):
            await studio.start_support_session(
                actor_user_id=support.user_id,
                tenant_id=workspace.tenant_id,
                reason=REASON,
                reference=None,
                scopes=("configuration",),
                duration_minutes=15,
            )
        with pytest.raises(PermissionError):
            await studio.authorize_support_read(
                actor_user_id=admin.user_id,
                session_id=session.session_id,
                scope="readiness",
            )
        with pytest.raises(PermissionError):
            await studio.authorize_support_read(
                actor_user_id=support.user_id,
                session_id=session.session_id,
                scope="configuration",
            )
        await studio.authorize_support_read(
            actor_user_id=support.user_id,
            session_id=session.session_id,
            scope="readiness",
        )
        viewed = await (
            await fixture.execute(
                "SELECT count(*), max(scope) FROM platform_audit_events "
                "WHERE action = 'platform_support.data_viewed' "
                "AND support_session_id = %s",
                (session.session_id,),
            )
        ).fetchone()
        assert viewed == (1, "readiness")

        # Expiry is decided by the database clock: a session created two hours
        # ago with a 30-minute window is closed.
        expired_row = await (
            await fixture.execute(
                """
                INSERT INTO platform_support_sessions
                    (actor_user_id, tenant_id, reason, scopes, created_at, expires_at)
                VALUES (%s, %s, %s, ARRAY['configuration'],
                    NOW() - INTERVAL '2 hours', NOW() - INTERVAL '90 minutes')
                RETURNING session_id
                """,
                (admin.user_id, workspace.tenant_id, REASON),
            )
        ).fetchone()
        assert expired_row is not None
        expired = await studio.get_support_session(expired_row[0])
        assert expired.state == "expired"
        with pytest.raises(SupportSessionClosedError):
            await studio.authorize_support_read(
                actor_user_id=admin.user_id,
                session_id=expired_row[0],
                scope="configuration",
            )

        ended = await studio.end_support_session(
            actor_user_id=admin.user_id,
            session_id=session.session_id,
            reason="Closing after handover to engineering",
            may_end_any=True,
        )
        assert ended.state == "ended"
        active = await studio.list_support_sessions(state="active", limit=10)
        assert session.session_id not in {item.session_id for item in active}

        for statement, params in (
            (
                "INSERT INTO platform_support_sessions "
                "(actor_user_id, tenant_id, reason, scopes, expires_at) "
                "VALUES (%s, %s, %s, ARRAY['transcripts'], "
                "NOW() + INTERVAL '5 minutes')",
                (admin.user_id, workspace.tenant_id, REASON),
            ),
            (
                "INSERT INTO platform_support_sessions "
                "(actor_user_id, tenant_id, reason, scopes, expires_at) "
                "VALUES (%s, %s, %s, ARRAY['readiness'], NOW() + INTERVAL '2 hours')",
                (admin.user_id, workspace.tenant_id, REASON),
            ),
            (
                "INSERT INTO platform_support_sessions "
                "(actor_user_id, tenant_id, reason, scopes, expires_at) "
                "VALUES (%s, %s, 'short', ARRAY['readiness'], "
                "NOW() + INTERVAL '5 minutes')",
                (admin.user_id, workspace.tenant_id),
            ),
        ):
            with pytest.raises(errors.CheckViolation):
                async with fixture.transaction():
                    await fixture.execute(statement, params)

        with pytest.raises(errors.InsufficientPrivilege):
            async with fixture.transaction():
                await fixture.execute("SET LOCAL ROLE ucve_app")
                await fixture.execute("SELECT count(*) FROM platform_support_sessions")
    finally:
        await fixture.close()
        await database.close()
