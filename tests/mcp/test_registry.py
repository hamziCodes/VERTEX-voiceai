from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from core.mcp.host import MCPServerConfig, MCPTransportType
from core.mcp.registry import (
    InMemoryMCPRegistry,
    MCPRegistryConflictError,
    MCPServerNotFoundError,
)
from core.providers.interfaces.llm import ToolDefinition

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "db"
    / "migrations"
    / "023_mcp_registry.sql"
)


def test_mcp_migration_is_tenant_scoped_and_disabled_by_default() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in ("mcp_servers", "mcp_server_tools"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql
        assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql
        assert f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY" in sql
    assert "enabled BOOLEAN NOT NULL DEFAULT FALSE" in sql
    assert "credential_ref" in sql
    assert "credential_value" not in sql
    assert "UNIQUE (tenant_id, tool_name)" in sql


@pytest.mark.parametrize(
    "endpoint",
    (
        "http://mcp.example.test/rpc",
        "https://user:password@mcp.example.test/rpc",
        "https://mcp.example.test/rpc#fragment",
    ),
)
def test_registry_config_rejects_unsafe_http_metadata(endpoint: str) -> None:
    with pytest.raises(ValueError, match="endpoint"):
        MCPServerConfig(endpoint=endpoint)


@pytest.mark.asyncio
async def test_registry_enforces_tenant_ownership() -> None:
    tenant_a = uuid4()
    tenant_b = uuid4()
    config = MCPServerConfig(
        tenant_id=tenant_a,
        name="Inventory",
        endpoint="https://mcp.example.test/rpc",
        enabled=True,
    )
    registry = InMemoryMCPRegistry()
    await registry.register(config)

    assert (await registry.get(tenant_a, config.server_id)).name == "Inventory"
    with pytest.raises(MCPServerNotFoundError):
        await registry.get(tenant_b, config.server_id)


@pytest.mark.asyncio
async def test_registry_rejects_duplicate_enabled_tool_owner() -> None:
    tenant_id = uuid4()
    registry = InMemoryMCPRegistry()
    first = MCPServerConfig(
        tenant_id=tenant_id,
        name="First",
        endpoint="https://first.example.test/mcp",
        enabled=True,
        allowed_tools=("lookup_order",),
    )
    second = MCPServerConfig(
        tenant_id=tenant_id,
        name="Second",
        endpoint="https://second.example.test/mcp",
        enabled=True,
        allowed_tools=("lookup_order",),
    )
    tool = ToolDefinition(
        name="lookup_order",
        description="Look up an order",
        parameters={"type": "object"},
    )
    await registry.register(first)
    await registry.replace_inventory(tenant_id, first.server_id, [tool])
    await registry.register(second)

    with pytest.raises(MCPRegistryConflictError, match="duplicate_tool_owner"):
        await registry.replace_inventory(tenant_id, second.server_id, [tool])


@pytest.mark.asyncio
async def test_side_effect_tool_requires_server_idempotency_support() -> None:
    tenant_id = uuid4()
    registry = InMemoryMCPRegistry()
    config = MCPServerConfig(
        tenant_id=tenant_id,
        name="Actions",
        endpoint="https://actions.example.test/mcp",
        enabled=True,
        allowed_tools=("create_booking",),
        side_effecting_tools=("create_booking",),
    )
    await registry.register(config)
    tool = ToolDefinition(
        name="create_booking",
        description="Create a booking",
        parameters={"type": "object"},
    )

    with pytest.raises(MCPRegistryConflictError, match="idempotency_not_supported"):
        await registry.replace_inventory(tenant_id, config.server_id, [tool])


@pytest.mark.asyncio
async def test_registry_lists_only_enabled_servers_for_tenant() -> None:
    tenant_id = uuid4()
    registry = InMemoryMCPRegistry()
    enabled = MCPServerConfig(
        tenant_id=tenant_id,
        name="Enabled",
        endpoint="https://enabled.example.test/mcp",
        enabled=True,
    )
    disabled = MCPServerConfig(
        tenant_id=tenant_id,
        name="Disabled",
        endpoint="https://disabled.example.test/mcp",
    )
    await registry.register(enabled)
    await registry.register(disabled)

    assert await registry.list_enabled(tenant_id) == [enabled]
    assert disabled.transport is MCPTransportType.STREAMABLE_HTTP
