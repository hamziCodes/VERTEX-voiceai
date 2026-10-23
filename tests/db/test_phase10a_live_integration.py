from __future__ import annotations

import asyncio
import os
import sys
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
async def test_phase10a_migration_vector_profile_and_knowledge_rls() -> None:
    import psycopg

    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)

    tenant_a = uuid4()
    tenant_b = uuid4()
    base_a = uuid4()
    base_b = uuid4()
    agent_id = uuid4()
    version_id = uuid4()
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "phase10a-a", tenant_b, "phase10a-b"),
            )
            await connection.execute(
                "INSERT INTO knowledge_bases (id, tenant_id, name) "
                "VALUES (%s, %s, %s), (%s, %s, %s)",
                (base_a, tenant_a, "A docs", base_b, tenant_b, "B docs"),
            )
            await connection.execute(
                "UPDATE knowledge_bases SET status = 'active', active_revision = 1 "
                "WHERE id = %s",
                (base_a,),
            )
            await connection.execute(
                "INSERT INTO agent_configs "
                "(agent_id, tenant_id, name, current_version, draft_data) "
                "VALUES (%s, %s, %s, 1, %s::jsonb)",
                (agent_id, tenant_a, "phase10a-agent", "{}"),
            )
            await connection.execute(
                "INSERT INTO agent_config_versions "
                "(version_id, agent_id, tenant_id, version, config_snapshot) "
                "VALUES (%s, %s, %s, 1, %s::jsonb)",
                (version_id, agent_id, tenant_a, "{}"),
            )

        async with connection.transaction():
            await connection.execute("SET LOCAL ROLE ucve_app")
            await connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_a),)
            )
            rows = await (
                await connection.execute("SELECT id FROM knowledge_bases ORDER BY id")
            ).fetchall()
            assert rows == [(base_a,)]

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE ucve_app")
                await connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)",
                    (str(tenant_a),),
                )
                await connection.execute(
                    "INSERT INTO knowledge_bases (tenant_id, name) VALUES (%s, %s)",
                    (tenant_b, "cross-tenant-denied"),
                )

        async with connection.transaction():
            cursor = await connection.execute(
                "SELECT format_type(a.atttypid, a.atttypmod) "
                "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
                "WHERE c.relname = 'knowledge_chunks' "
                "AND a.attname = 'embedding'"
            )
            assert (await cursor.fetchone())[0] == "vector(384)"
    finally:
        await connection.close()

    from core.db.async_pg import AsyncDatabase
    from core.db.repos.knowledge_repo import PostgresKnowledgeRepository

    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=1)
    await database.open()
    try:
        from core.db.repos.knowledge_repo import KnowledgeNotFoundError

        repository = PostgresKnowledgeRepository(database)
        created = await repository.create_knowledge_base(tenant_a, "Repository docs")
        assert created.tenant_id == tenant_a
        listed_ids = {
            item.knowledge_base_id
            for item in await repository.list_knowledge_bases(tenant_a)
        }
        assert listed_ids == {base_a, created.knowledge_base_id}
        with pytest.raises(KnowledgeNotFoundError):
            await repository.get_knowledge_base(tenant_b, base_a)
        first = await repository.record_binding(tenant_a, agent_id, 1, base_a, 1)
        second = await repository.record_binding(tenant_a, agent_id, 1, base_a, 1)
        assert second.binding_id == first.binding_id
    finally:
        await database.close()

    assert await apply_migrations_async(database_url) == []
