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
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_disposable_post_call_lifecycle_restart_idempotency_and_rls() -> None:
    import psycopg

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.post_call_repo import (
        PostCallNotFoundError,
        PostgresPostCallRepository,
    )
    from infra.db.migrate import apply_migrations_async
    from post_call.models.diarized_turn import DiarizedTurn
    from post_call.models.disposition import CallDisposition
    from post_call.models.policy import PostCallPolicy
    from post_call.models.recording import CallRecording, RecordingState

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_a, tenant_b, agent_id, session_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "phase11-a", tenant_b, "phase11-b"),
            )
            await connection.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                (agent_id, tenant_a, "phase11-agent"),
            )
    finally:
        await connection.close()

    started_at = datetime(2026, 10, 26, 10, 30, tzinfo=UTC)
    first_database = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await first_database.open()
    try:
        first_repo = PostgresPostCallRepository(first_database)
        call = await first_repo.start_call(
            tenant_id=tenant_a,
            agent_id=agent_id,
            session_id=session_id,
            started_at=started_at,
            transport_type="websocket",
            policy=PostCallPolicy(storage_region="pk-isb"),
            provider_snapshot={"stt": "gladia"},
        )
        await first_repo.append_turn(
            tenant_id=tenant_a,
            session_id=session_id,
            ordinal=0,
            turn=DiarizedTurn(
                speaker="user", text="Generated transcript.", start_ms=0, end_ms=100
            ),
        )
    finally:
        await first_database.close()

    restarted_database = AsyncDatabase(
        database_url=database_url, min_size=1, max_size=1
    )
    await restarted_database.open()
    try:
        restarted_repo = PostgresPostCallRepository(restarted_database)
        duplicate = await restarted_repo.start_call(
            tenant_id=tenant_a,
            agent_id=agent_id,
            session_id=session_id,
            started_at=started_at + timedelta(hours=1),
            transport_type="sip",
            policy=PostCallPolicy(storage_region="another-region"),
            provider_snapshot={"stt": "other"},
        )
        assert duplicate.call_id == call.call_id
        assert duplicate.started_at == started_at
        assert len(duplicate.turns) == 1

        finalized = await restarted_repo.finalize_call(
            tenant_id=tenant_a,
            session_id=session_id,
            ended_at=started_at + timedelta(seconds=9),
            end_reason="complete",
            disposition=CallDisposition.COMPLETED,
            metrics_snapshot={"turns": 1},
            usage_snapshot={"agent_sec": 9.0},
            recording_state=RecordingState.NOT_REQUESTED,
        )
        second_finalize = await restarted_repo.finalize_call(
            tenant_id=tenant_a,
            session_id=session_id,
            ended_at=started_at + timedelta(hours=2),
            end_reason="overwrite",
            disposition=CallDisposition.UNRESOLVED,
            metrics_snapshot={},
            usage_snapshot={},
            recording_state=RecordingState.FAILED,
            recording_error_code="late",
        )
        assert second_finalize.ended_at == finalized.ended_at
        assert second_finalize.end_reason == "complete"
        with pytest.raises(PostCallNotFoundError):
            await restarted_repo.get_call(tenant_b, session_id)

        recorded_session_id = uuid4()
        await restarted_repo.start_call(
            tenant_id=tenant_a,
            agent_id=agent_id,
            session_id=recorded_session_id,
            started_at=started_at,
            transport_type="sip",
            policy=PostCallPolicy(
                recording_enabled=True,
                recording_consent_obtained=True,
                storage_region="pk-isb",
            ),
            provider_snapshot={},
        )
        recording = CallRecording(
            recording_s3_uri="objects://pk-isb/tenant/recorded.wav",
            checksum="d" * 64,
            channel_count=2,
            dual_channel=True,
            duration_sec=8.5,
            storage_region="pk-isb",
        )
        recorded = await restarted_repo.finalize_call(
            tenant_id=tenant_a,
            session_id=recorded_session_id,
            ended_at=started_at + timedelta(seconds=9),
            end_reason="complete",
            disposition=CallDisposition.COMPLETED,
            metrics_snapshot={},
            usage_snapshot={},
            recording_state=RecordingState.AVAILABLE,
            recording=recording,
        )
        assert recorded.recording == recording

        async with restarted_database.tenant_transaction(str(tenant_a)) as db:
            with pytest.raises(psycopg.errors.CheckViolation):
                await db.execute(
                    "UPDATE call_records SET recording_s3_uri = %s "
                    "WHERE tenant_id = %s::uuid AND session_id = %s::uuid",
                    (
                        "objects://pk-isb/hidden.wav",
                        str(tenant_a),
                        str(session_id),
                    ),
                )
    finally:
        await restarted_database.close()

    rls_connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with rls_connection.transaction():
            await rls_connection.execute("SET LOCAL ROLE ucve_app")
            await rls_connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),)
            )
            assert (
                await (
                    await rls_connection.execute("SELECT call_id FROM call_records")
                ).fetchall()
                == []
            )
            assert (
                await (
                    await rls_connection.execute("SELECT id FROM call_record_turns")
                ).fetchall()
                == []
            )
    finally:
        await rls_connection.close()

    assert await apply_migrations_async(database_url) == []
