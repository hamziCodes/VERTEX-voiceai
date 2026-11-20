from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    """Psycopg async requires a selector loop on Windows."""
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase13_fresh_schema_rls_concurrency_secrets_and_pagination() -> None:
    import psycopg

    from control_plane.agents.models.agent_config import AgentConfig
    from control_plane.agents.pg_repo import PostgresAgentConfigRepo
    from control_plane.agents.repo import AgentRevisionConflictError
    from control_plane.auth.api_keys_async import AsyncAPIKeyManager
    from control_plane.studio.models import IdentityContext
    from control_plane.studio.pg_repository import PostgresStudioRepository
    from control_plane.studio.repository import InvitationConsumedError
    from core.db.async_pg import AsyncDatabase
    from core.db.repos.post_call_repo import PostgresPostCallRepository
    from core.secrets.kms.local_dev import LocalDevKMSBackend
    from core.secrets.repository import PostgresSecretRepository
    from core.secrets.vault import SecretVault
    from infra.db.migrate import apply_migrations_async
    from post_call.models.diarized_turn import DiarizedTurn
    from post_call.models.policy import PostCallPolicy

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=2)
    await database.open()
    try:
        studio = PostgresStudioRepository(database)
        owner = await studio.resolve_identity(
            IdentityContext(
                issuer="https://phase13.test",
                subject="owner",
                email="owner@phase13.test",
            )
        )
        member = await studio.resolve_identity(
            IdentityContext(
                issuer="https://phase13.test",
                subject="member",
                email="member@phase13.test",
            )
        )
        workspace = await studio.create_workspace(owner.user_id, "Phase 13 A")
        other_workspace = await studio.create_workspace(member.user_id, "Phase 13 B")
        invitation_hash = "a" * 64
        await studio.create_invitation(
            workspace.tenant_id,
            email="member@phase13.test",
            role="tenant_editor",
            token_hash=invitation_hash,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            invited_by=owner.user_id,
        )
        accepted = await studio.accept_invitation(invitation_hash, member.user_id)
        assert accepted.tenant_id == workspace.tenant_id
        with pytest.raises(InvitationConsumedError):
            await studio.accept_invitation(invitation_hash, member.user_id)

        fixture = await psycopg.AsyncConnection.connect(database_url)
        try:
            async with fixture.transaction():
                await fixture.execute(
                    "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                    (agent_id := uuid4(), workspace.tenant_id, "Phase 13 agent"),
                )
            async with fixture.transaction():
                await fixture.execute("SET LOCAL ROLE ucve_app")
                await fixture.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(other_workspace.tenant_id),),
                )
                count = await (
                    await fixture.execute("SELECT COUNT(*) FROM workspace_invitations")
                ).fetchone()
                assert count == (0,)
        finally:
            await fixture.close()

        agents = PostgresAgentConfigRepo(database)
        draft = await agents.create_agent(
            AgentConfig(
                tenant_id=workspace.tenant_id,
                agent_id=agent_id,
                name="Phase 13 agent",
            )
        )
        saved, did_save = await agents.save_draft_autosave(
            workspace.tenant_id,
            agent_id,
            {"description": "first writer"},
            force=True,
            expected_revision=draft.draft_revision,
        )
        assert did_save and saved.draft_revision == 2
        with pytest.raises(AgentRevisionConflictError):
            await agents.save_draft_autosave(
                workspace.tenant_id,
                agent_id,
                {"description": "stale writer"},
                force=True,
                expected_revision=draft.draft_revision,
            )

        vault = SecretVault(
            kms_backend=LocalDevKMSBackend(master_key="phase13-disposable-test-key"),
            repository=PostgresSecretRepository(database),
        )
        secret_value = "phase13-disposable-provider-value"
        await vault.astore(
            str(workspace.tenant_id),
            "groq",
            secret_value,
            credential_ref="primary",
        )
        credential_records = await vault.alist_records(str(workspace.tenant_id))
        assert len(credential_records) == 1
        assert secret_value not in repr(credential_records)
        assert credential_records[0].encrypted_blob != secret_value

        key_manager = AsyncAPIKeyManager(database)
        raw_key, _ = await key_manager.generate_api_key(
            str(workspace.tenant_id), "phase13-disposable"
        )
        key_records = await key_manager.list_api_keys(str(workspace.tenant_id))
        assert len(key_records) == 1
        assert raw_key not in repr(key_records)

        calls = PostgresPostCallRepository(database)
        started = datetime.now(UTC)
        for offset in range(3):
            session_id = uuid4()
            await calls.start_call(
                tenant_id=workspace.tenant_id,
                agent_id=agent_id,
                session_id=session_id,
                started_at=started - timedelta(minutes=offset),
                transport_type="websocket",
                policy=PostCallPolicy(),
                provider_snapshot={"stt": "offline"},
            )
            await calls.append_turn(
                tenant_id=workspace.tenant_id,
                session_id=session_id,
                ordinal=0,
                turn=DiarizedTurn(
                    speaker="user",
                    text=f"turn {offset}",
                    start_ms=0,
                    end_ms=10,
                ),
            )
        first_page = await calls.list_calls(workspace.tenant_id, limit=2)
        cursor = (first_page[-1].started_at, first_page[-1].call_id)
        second_page = await calls.list_calls(
            workspace.tenant_id, before=cursor, limit=2
        )
        assert len(first_page) == 2
        assert len(second_page) == 1
        assert {item.call_id for item in first_page}.isdisjoint(
            {item.call_id for item in second_page}
        )
        assert all(len(item.turns) == 1 for item in (*first_page, *second_page))
    finally:
        await database.close()

    assert await apply_migrations_async(database_url) == []
