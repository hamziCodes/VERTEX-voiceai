"""Tool Orchestrator — Merges builtin + tenant MCP tools & serializes execution."""

from __future__ import annotations

import asyncio
from typing import Any

from core.mcp.builtin_tools import (
    BUILTIN_TOOLS,
    handle_end_conversation_summary,
    handle_escalate_to_human,
)
from core.mcp.host import MCPConfigurationError, MCPHost, MCPToolResult
from core.providers.interfaces.llm import ToolDefinition


class ToolOrchestrator:
    """Orchestrates builtin tools and registered tenant MCP hosts serially."""

    def __init__(self, mcp_hosts: list[MCPHost] | None = None) -> None:
        self.mcp_hosts = mcp_hosts or []
        self.builtin_tools = BUILTIN_TOOLS
        self.executed_tools: list[str] = []
        self._tool_owners: dict[str, MCPHost] = {}

    async def get_external_tools(self) -> list[ToolDefinition]:
        """Return connected tenant tools and build an unambiguous owner map."""
        tools: list[ToolDefinition] = []
        owners: dict[str, MCPHost] = {}
        for host in self.mcp_hosts:
            if not host.is_connected:
                continue
            for tool in await host.list_tools():
                if tool.name in owners:
                    raise MCPConfigurationError(
                        f"Duplicate MCP tool owner for {tool.name!r}."
                    )
                owners[tool.name] = host
                tools.append(tool)
        self._tool_owners = owners
        return tools

    async def get_all_tools(self) -> list[ToolDefinition]:
        """Return combined list of builtin tools + all tenant MCP server tools."""
        return [*self.builtin_tools, *(await self.get_external_tools())]

    async def execute_tool_call_serially(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Execute a tool call serially (v1 policy).

        Returns DATA-framed tool result dictionary with role='tool'.
        """
        self.executed_tools.append(name)

        # 1. Check Builtin Tools
        if name == "end_conversation_summary":
            result = await handle_end_conversation_summary(arguments)
            return {
                "role": "tool",
                "name": name,
                "content": str(result),
                "data_framed": True,
            }

        if name == "escalate_to_human":
            result = await handle_escalate_to_human(arguments)
            return {
                "role": "tool",
                "name": name,
                "content": str(result),
                "data_framed": True,
            }

        if not self._tool_owners:
            await self.get_external_tools()
        owner = self._tool_owners.get(name)
        if owner is not None:
            mcp_res: MCPToolResult = await owner.call_tool(
                name, arguments, idempotency_key=idempotency_key
            )
            return {
                "role": "tool",
                "name": name,
                "content": mcp_res.content,
                "is_error": mcp_res.is_error,
                "data_framed": True,
            }

        return {
            "role": "tool",
            "name": name,
            "content": f"Error: Tool '{name}' not found",
            "is_error": True,
            "data_framed": True,
        }

    async def close(self) -> None:
        """Close every connected MCP transport and clear owner state."""
        self._tool_owners.clear()
        await asyncio.gather(
            *(host.close() for host in self.mcp_hosts), return_exceptions=True
        )
