"""Tenant-owned durable MCP server and tool registry."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from core.db.async_pg import AsyncDatabase, get_default_database
from core.mcp.host import MCPServerConfig, MCPTransportType, validate_tool_schema
from core.providers.interfaces.llm import ToolDefinition


class MCPRegistryConflictError(RuntimeError):
    pass


class MCPServerNotFoundError(LookupError):
    pass


class InMemoryMCPRegistry:
    """Deterministic local registry with the PostgreSQL ownership contract."""

    def __init__(self) -> None:
        self._servers: dict[tuple[UUID, UUID], MCPServerConfig] = {}
        self._tools: dict[tuple[UUID, UUID], list[ToolDefinition]] = {}

    async def register(self, config: MCPServerConfig) -> MCPServerConfig:
        if any(
            tenant == config.tenant_id
            and existing.name.casefold() == config.name.casefold()
            and server_id != config.server_id
            for (tenant, server_id), existing in self._servers.items()
        ):
            raise MCPRegistryConflictError("server_name_exists")
        self._servers[(config.tenant_id, config.server_id)] = config
        return config

    async def get(self, tenant_id: UUID, server_id: UUID) -> MCPServerConfig:
        try:
            return self._servers[(tenant_id, server_id)]
        except KeyError as exc:
            raise MCPServerNotFoundError("MCP server not found.") from exc

    async def list_enabled(self, tenant_id: UUID) -> list[MCPServerConfig]:
        return sorted(
            (
                config
                for (owner, _), config in self._servers.items()
                if owner == tenant_id and config.enabled
            ),
            key=lambda item: (item.name.casefold(), str(item.server_id)),
        )

    async def replace_inventory(
        self,
        tenant_id: UUID,
        server_id: UUID,
        tools: list[ToolDefinition],
    ) -> list[ToolDefinition]:
        config = await self.get(tenant_id, server_id)
        names = [tool.name for tool in tools]
        if len(names) != len(set(names)):
            raise MCPRegistryConflictError("duplicate_tool_name")
        selected = [tool for tool in tools if tool.name in config.allowed_tools]
        for tool in selected:
            validate_tool_schema(tool.parameters)
            if (
                tool.name in config.side_effecting_tools
                and tool.name not in config.idempotency_supported_tools
            ):
                raise MCPRegistryConflictError("idempotency_not_supported")
            for (owner, other_id), other_tools in self._tools.items():
                other = self._servers.get((owner, other_id))
                if (
                    owner == tenant_id
                    and other_id != server_id
                    and other is not None
                    and other.enabled
                    and any(item.name == tool.name for item in other_tools)
                ):
                    raise MCPRegistryConflictError("duplicate_tool_owner")
        self._tools[(tenant_id, server_id)] = list(selected)
        return list(selected)


class PostgresMCPRegistry:
    """PostgreSQL registry using transaction-local tenant RLS context."""

    def __init__(self, database: AsyncDatabase | None = None) -> None:
        self.database = database or get_default_database()

    async def register(self, config: MCPServerConfig) -> MCPServerConfig:
        async with self.database.tenant_transaction(str(config.tenant_id)) as conn:
            await conn.execute(
                """
                INSERT INTO mcp_servers (
                    id, tenant_id, name, transport, endpoint, credential_ref,
                    enabled, allowed_tools, side_effecting_tools,
                    idempotency_supported_tools
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb
                )
                ON CONFLICT (tenant_id, id) DO UPDATE SET
                    name = EXCLUDED.name,
                    transport = EXCLUDED.transport,
                    endpoint = EXCLUDED.endpoint,
                    credential_ref = EXCLUDED.credential_ref,
                    enabled = EXCLUDED.enabled,
                    allowed_tools = EXCLUDED.allowed_tools,
                    side_effecting_tools = EXCLUDED.side_effecting_tools,
                    idempotency_supported_tools = EXCLUDED.idempotency_supported_tools,
                    updated_at = NOW()
                """,
                (
                    str(config.server_id),
                    str(config.tenant_id),
                    config.name,
                    config.transport.value,
                    config.endpoint,
                    config.credential_ref,
                    config.enabled,
                    json.dumps(config.allowed_tools),
                    json.dumps(config.side_effecting_tools),
                    json.dumps(config.idempotency_supported_tools),
                ),
            )
        return config

    async def get(self, tenant_id: UUID, server_id: UUID) -> MCPServerConfig:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                """
                SELECT id, tenant_id, name, transport, endpoint, credential_ref,
                       enabled, allowed_tools, side_effecting_tools,
                       idempotency_supported_tools
                FROM mcp_servers WHERE tenant_id = %s AND id = %s
                """,
                (str(tenant_id), str(server_id)),
            )
            row = await cursor.fetchone()
        if row is None:
            raise MCPServerNotFoundError("MCP server not found.")
        return _config_from_row(row)

    async def list_enabled(self, tenant_id: UUID) -> list[MCPServerConfig]:
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                """
                SELECT id, tenant_id, name, transport, endpoint, credential_ref,
                       enabled, allowed_tools, side_effecting_tools,
                       idempotency_supported_tools
                FROM mcp_servers
                WHERE tenant_id = %s AND enabled = TRUE
                ORDER BY lower(name), id
                """,
                (str(tenant_id),),
            )
            rows = await cursor.fetchall()
        return [_config_from_row(row) for row in rows]

    async def replace_inventory(
        self,
        tenant_id: UUID,
        server_id: UUID,
        tools: list[ToolDefinition],
    ) -> list[ToolDefinition]:
        config = await self.get(tenant_id, server_id)
        selected = [tool for tool in tools if tool.name in config.allowed_tools]
        if len({tool.name for tool in selected}) != len(selected):
            raise MCPRegistryConflictError("duplicate_tool_name")
        for tool in selected:
            validate_tool_schema(tool.parameters)
            if (
                tool.name in config.side_effecting_tools
                and tool.name not in config.idempotency_supported_tools
            ):
                raise MCPRegistryConflictError("idempotency_not_supported")
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            for tool in selected:
                cursor = await conn.execute(
                    """
                    SELECT server_id FROM mcp_server_tools
                    WHERE tenant_id = %s AND tool_name = %s AND server_id <> %s
                    """,
                    (str(tenant_id), tool.name, str(server_id)),
                )
                if await cursor.fetchone() is not None:
                    raise MCPRegistryConflictError("duplicate_tool_owner")
            await conn.execute(
                "DELETE FROM mcp_server_tools WHERE tenant_id = %s AND server_id = %s",
                (str(tenant_id), str(server_id)),
            )
            for tool in selected:
                await conn.execute(
                    """
                    INSERT INTO mcp_server_tools (
                        tenant_id, server_id, tool_name, description, input_schema,
                        side_effecting, idempotency_supported
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        str(tenant_id),
                        str(server_id),
                        tool.name,
                        tool.description,
                        json.dumps(tool.parameters),
                        tool.name in config.side_effecting_tools,
                        tool.name in config.idempotency_supported_tools,
                    ),
                )
        return selected


def _config_from_row(row: Any) -> MCPServerConfig:
    return MCPServerConfig(
        server_id=UUID(str(row[0])),
        tenant_id=UUID(str(row[1])),
        name=str(row[2]),
        transport=MCPTransportType(str(row[3])),
        endpoint=str(row[4]),
        credential_ref=str(row[5]) if row[5] is not None else None,
        enabled=bool(row[6]),
        allowed_tools=tuple(row[7] or ()),
        side_effecting_tools=tuple(row[8] or ()),
        idempotency_supported_tools=tuple(row[9] or ()),
    )
