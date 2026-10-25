"""Tool Orchestrator — Merges builtin + tenant MCP tools & serializes execution."""

from __future__ import annotations

from typing import Any

from core.mcp.builtin_tools import (
    BUILTIN_TOOLS,
    handle_end_conversation_summary,
    handle_escalate_to_human,
)
from core.mcp.host import MCPHost, MCPToolResult
from core.providers.interfaces.llm import ToolDefinition


class ToolOrchestrator:
    """Orchestrates builtin tools and registered tenant MCP hosts serially."""

    def __init__(self, mcp_hosts: list[MCPHost] | None = None) -> None:
        self.mcp_hosts = mcp_hosts or []
        self.builtin_tools = BUILTIN_TOOLS
        self.executed_tools: list[str] = []

    async def get_all_tools(self) -> list[ToolDefinition]:
        """Return combined list of builtin tools + all tenant MCP server tools."""
        combined = list(self.builtin_tools)
        for host in self.mcp_hosts:
            if host.is_connected:
                tenant_tools = await host.list_tools()
                combined.extend(tenant_tools)
        return combined

    async def execute_tool_call_serially(
        self, name: str, arguments: dict[str, Any]
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

        # 2. Check MCP Hosts
        for host in self.mcp_hosts:
            mcp_res: MCPToolResult = await host.call_tool(name, arguments)
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
