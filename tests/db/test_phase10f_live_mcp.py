from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
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
async def test_disposable_registry_persists_and_enforces_tenant_scope() -> None:
    import psycopg

    from core.mcp.host import MCPServerConfig
    from core.mcp.registry import (
        MCPServerNotFoundError,
        PostgresMCPRegistry,
    )
    from core.providers.interfaces.llm import ToolDefinition
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must name a disposable database"
    await apply_migrations_async(database_url)
    tenant_a, tenant_b = uuid4(), uuid4()
    connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with connection.transaction():
            await connection.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s), (%s, %s)",
                (tenant_a, "mcp-a", tenant_b, "mcp-b"),
            )
    finally:
        await connection.close()

    repository_connection = await psycopg.AsyncConnection.connect(database_url)

    class _ConnectionDatabase:
        @asynccontextmanager
        async def tenant_transaction(self, tenant_id: str) -> AsyncIterator[Any]:
            async with repository_connection.transaction():
                await repository_connection.execute(
                    "SELECT set_config('app.tenant_id', %s, true)", (tenant_id,)
                )
                yield repository_connection

    registry = PostgresMCPRegistry(_ConnectionDatabase())  # type: ignore[arg-type]
    config = MCPServerConfig(
        tenant_id=tenant_a,
        name="Inventory",
        endpoint="https://mcp.example.test/rpc",
        enabled=True,
        allowed_tools=("lookup_order",),
    )
    try:
        await registry.register(config)
        stored = await registry.get(tenant_a, config.server_id)
        assert stored.credential_ref is None
        assert stored.allowed_tools == ("lookup_order",)
        with pytest.raises(MCPServerNotFoundError):
            await registry.get(tenant_b, config.server_id)
        inventory = await registry.replace_inventory(
            tenant_a,
            config.server_id,
            [
                ToolDefinition(
                    "lookup_order",
                    "Lookup",
                    {"type": "object", "properties": {}},
                )
            ],
        )
        assert [tool.name for tool in inventory] == ["lookup_order"]
    finally:
        await repository_connection.close()

    rls_connection = await psycopg.AsyncConnection.connect(database_url)
    try:
        async with rls_connection.transaction():
            await rls_connection.execute("SET LOCAL ROLE ucve_app")
            await rls_connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_b),)
            )
            cursor = await rls_connection.execute("SELECT id FROM mcp_servers")
            assert await cursor.fetchall() == []
    finally:
        await rls_connection.close()
