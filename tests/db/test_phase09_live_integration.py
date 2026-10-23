from __future__ import annotations

import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.mark.asyncio
async def test_disposable_postgres_migrations_rls_vector_and_usage() -> None:
    import psycopg

    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)

    tenant_a = uuid4()
    tenant_b = uuid4()
    event_id = uuid4()
    event_key = f"phase09:{event_id}"
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "phase09-a", tenant_b, "phase09-b"),
            )
            vector_cursor = await connection.execute(
                "SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector"
            )
            distance = (await vector_cursor.fetchone())[0]
            assert float(distance) > 0
            for _attempt in range(2):
                await connection.execute(
                    "INSERT INTO usage_events "
                    "(id, tenant_id, usage_kind, quantity, event_key, unit) "
                    "VALUES (%s, %s, 'agent_sec', 1, %s, 'seconds') "
                    "ON CONFLICT (tenant_id, event_key) DO NOTHING",
                    (uuid4(), tenant_a, event_key),
                )
            count_cursor = await connection.execute(
                "SELECT COUNT(*) FROM usage_events "
                "WHERE tenant_id = %s AND event_key = %s",
                (tenant_a, event_key),
            )
            assert (await count_cursor.fetchone())[0] == 1

        async with connection.transaction():
            await connection.execute("SET LOCAL ROLE ucve_app")
            await connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (str(tenant_a),),
            )
            rows = await (
                await connection.execute("SELECT id FROM tenants ORDER BY id")
            ).fetchall()
            assert rows == [(tenant_a,)]

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE ucve_app")
                await connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tenant_a),),
                )
                await connection.execute(
                    "INSERT INTO agents (id, tenant_id, name) VALUES (%s, %s, %s)",
                    (uuid4(), tenant_b, "cross-tenant-denied"),
                )
    finally:
        await connection.close()

    reopened = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with reopened.transaction():
            cursor = await reopened.execute(
                "SELECT COUNT(*) FROM usage_events "
                "WHERE tenant_id = %s AND event_key = %s",
                (tenant_a, event_key),
            )
            assert (await cursor.fetchone())[0] == 1
    finally:
        await reopened.close()

    assert await apply_migrations_async(database_url) == []
