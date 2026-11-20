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


def _event(event_type: str, *, event_id=None, occurred_at=None):
    from telephony_gateway.telnyx.models import TelnyxWebhookEnvelope

    return TelnyxWebhookEnvelope.model_validate(
        {
            "data": {
                "id": str(event_id or uuid4()),
                "event_type": event_type,
                "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
                "record_type": "event",
                "payload": {
                    "call_control_id": "v3:phase12-disposable",
                    "call_leg_id": "phase12-leg",
                    "call_session_id": "phase12-carrier-session",
                    "connection_id": "phase12-connection",
                    "from": "+14155550100",
                    "to": "+18005550199",
                    "direction": "incoming",
                    "hangup_cause": "normal_clearing",
                },
            }
        }
    )


@pytest.mark.asyncio
async def test_disposable_telephony_identity_restart_idempotency_and_rls() -> None:
    import psycopg

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.telephony_repo import (
        PostgresTelephonyRepository,
        TelephonyCallState,
    )
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)

    tenant_a, tenant_b, agent_id, did_id = uuid4(), uuid4(), uuid4(), uuid4()
    version_id = uuid4()
    fixture = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with fixture.transaction():
            await fixture.execute(
                "INSERT INTO tenants (id, name) VALUES "
                "(%s, 'phase12-a'), (%s, 'phase12-b')",
                (tenant_a, tenant_b),
            )
            await fixture.execute(
                "INSERT INTO agents (id, tenant_id, name) "
                "VALUES (%s, %s, 'phase12-agent')",
                (agent_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO agent_configs "
                "(agent_id, tenant_id, name, current_version, draft_data) "
                "VALUES (%s, %s, 'phase12-agent', 1, '{}'::jsonb)",
                (agent_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO agent_config_versions "
                "(version_id, agent_id, tenant_id, version, config_snapshot) "
                "VALUES (%s, %s, %s, 1, %s::jsonb)",
                (version_id, agent_id, tenant_a, '{"is_published":true}'),
            )
            await fixture.execute(
                "INSERT INTO telephony_dids "
                "(id, tenant_id, agent_id, did_number, carrier, status) "
                "VALUES (%s, %s, %s, '+18005550199', 'telnyx', 'active')",
                (did_id, tenant_a, agent_id),
            )
            await fixture.execute(
                "INSERT INTO sip_trunks (tenant_id, credentials_ref) VALUES (%s, 'vault://phase12')",
                (tenant_a,),
            )
    finally:
        await fixture.close()

    initiated = _event("call.initiated")
    first_db = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await first_db.open()
    first_repo = PostgresTelephonyRepository(first_db)
    assert await first_repo.accept_once(initiated) is True
    first = await first_repo.get_call("telnyx", "v3:phase12-disposable")
    assert first is not None and first.state is TelephonyCallState.ADMITTED
    await first_db.close()

    second_db = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await second_db.open()
    second_repo = PostgresTelephonyRepository(second_db)
    assert await second_repo.accept_once(initiated) is False
    await second_repo.accept_once(
        _event("call.streaming.started", occurred_at=datetime.now(UTC))
    )
    await second_repo.accept_once(
        _event("call.answered", occurred_at=datetime.now(UTC) - timedelta(seconds=2))
    )
    current = await second_repo.get_call("telnyx", "v3:phase12-disposable")
    assert current is not None
    assert current.session_id == first.session_id
    assert current.state is TelephonyCallState.MEDIA_ACTIVE

    command = await second_repo.reserve_command(
        call_id=current.call_id,
        tenant_id=tenant_a,
        command_name="answer",
        idempotency_key="answer:v3:phase12-disposable",
    )
    duplicate_command = await second_repo.reserve_command(
        call_id=current.call_id,
        tenant_id=tenant_a,
        command_name="answer",
        idempotency_key="answer:v3:phase12-disposable",
    )
    assert duplicate_command.command_id == command.command_id
    await second_db.close()

    verify = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with verify.transaction():
            counts = await (
                await verify.execute(
                    "SELECT (SELECT COUNT(*) FROM telephony_calls), "
                    "(SELECT COUNT(*) FROM telephony_events), "
                    "(SELECT COUNT(*) FROM telephony_commands)"
                )
            ).fetchone()
            assert counts == (1, 3, 1)

        expected_by_tenant = {
            tenant_a: {
                "telephony_dids": 1,
                "sip_trunks": 1,
                "telephony_calls": 1,
                "telephony_events": 3,
                "telephony_commands": 1,
            },
            tenant_b: {
                "telephony_dids": 0,
                "sip_trunks": 0,
                "telephony_calls": 0,
                "telephony_events": 0,
                "telephony_commands": 0,
            },
        }
        for tenant_id, expected in expected_by_tenant.items():
            async with verify.transaction():
                await verify.execute("SET LOCAL ROLE ucve_app")
                await verify.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tenant_id),),
                )
                for table in (
                    "telephony_dids",
                    "sip_trunks",
                    "telephony_calls",
                    "telephony_events",
                    "telephony_commands",
                ):
                    count = await (
                        await verify.execute(f"SELECT COUNT(*) FROM {table}")
                    ).fetchone()
                    assert count[0] == expected[table]
    finally:
        await verify.close()

    assert await apply_migrations_async(database_url) == []
