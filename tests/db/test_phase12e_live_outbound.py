from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
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
async def test_disposable_outbound_policy_idempotency_limits_and_rls() -> None:
    import psycopg

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.outbound_call_repo import PostgresOutboundCallRepository
    from infra.db.migrate import apply_migrations_async
    from telephony_gateway.outbound import (
        OutboundCallError,
        OutboundCallRequest,
        OutboundCallStatus,
    )

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)

    tenant_a, tenant_b, agent_id, did_id = uuid4(), uuid4(), uuid4(), uuid4()
    version_id, trunk_id = uuid4(), uuid4()
    fixture = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with fixture.transaction():
            await fixture.execute(
                "INSERT INTO tenants (id, name) VALUES "
                "(%s, 'phase12e-a'), (%s, 'phase12e-b')",
                (tenant_a, tenant_b),
            )
            await fixture.execute(
                "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, 'agent')",
                (agent_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO agent_configs "
                "(agent_id, tenant_id, name, current_version, draft_data) "
                "VALUES (%s, %s, 'agent', 1, '{}'::jsonb)",
                (agent_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO agent_config_versions "
                "(version_id, agent_id, tenant_id, version, config_snapshot) "
                "VALUES (%s, %s, %s, 1, '{\"is_published\":true}'::jsonb)",
                (version_id, agent_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO telephony_dids "
                "(id, tenant_id, agent_id, did_number, carrier, status) "
                "VALUES (%s, %s, %s, '+14155550100', 'telnyx', 'active')",
                (did_id, tenant_a, agent_id),
            )
            await fixture.execute(
                "INSERT INTO sip_trunks "
                "(id, tenant_id, provider, credentials_ref, connection_id) "
                "VALUES (%s, %s, 'telnyx', 'tenant-key', 'connection-123')",
                (trunk_id, tenant_a),
            )
            await fixture.execute(
                "INSERT INTO telephony_outbound_policies "
                "(tenant_id, enabled, allowed_destinations, calling_timezone, "
                "window_start, window_end, max_concurrent_calls, "
                "max_calls_per_minute, daily_spend_cap_cents, "
                "reserved_spend_cents_per_call, max_call_duration_seconds) "
                "VALUES (%s, TRUE, ARRAY['+14155550199'], 'UTC', '00:00', "
                "'23:59:59', 1, 2, 50, 10, 300)",
                (tenant_a,),
            )
    finally:
        await fixture.close()

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await database.open()
    repository = PostgresOutboundCallRepository(
        database=database,
        media_stream_url="wss://voice.example.test/v1/telephony/media",
    )
    policy = await repository.get_policy(tenant_a)
    now = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
    request = OutboundCallRequest(
        tenant_id=tenant_a,
        agent_id=agent_id,
        destination="+14155550199",
        purpose="appointment reminder",
        consent_reference="consent-42",
        idempotency_key="phase12e-request-001",
    )
    first, created = await repository.reserve(request, policy, now)
    duplicate, duplicate_created = await repository.reserve(request, policy, now)
    assert created is True and duplicate_created is False
    assert duplicate.request_id == first.request_id
    with pytest.raises(OutboundCallError, match="concurrency_limit"):
        await repository.reserve(
            OutboundCallRequest(
                tenant_id=tenant_a,
                agent_id=agent_id,
                destination="+14155550199",
                purpose="second",
                consent_reference="consent-43",
                idempotency_key="phase12e-request-002",
            ),
            policy,
            now,
        )
    await repository.set_status(
        tenant_a, first.request_id, OutboundCallStatus.ENDED
    )
    await database.close()

    verify = await psycopg.AsyncConnection.connect(database_url)
    try:
        for tenant_id, expected in ((tenant_a, 1), (tenant_b, 0)):
            async with verify.transaction():
                await verify.execute("SET LOCAL ROLE ucve_app")
                await verify.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tenant_id),),
                )
                count = await (
                    await verify.execute(
                        "SELECT COUNT(*) FROM telephony_outbound_requests"
                    )
                ).fetchone()
                assert count[0] == expected
    finally:
        await verify.close()

    assert await apply_migrations_async(database_url) == []
