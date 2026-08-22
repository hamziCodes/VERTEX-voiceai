"""MCP Host Client — Config models, tool execution result & timeout bounds."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from core.providers.interfaces.llm import ToolDefinition


class MCPTransportType(str, Enum):
    """Supported MCP transport protocols."""

    STREAMABLE_HTTP = "streamable_http"
    SSE = "sse"
    STDIO = "stdio"


@dataclass
class ToolTimeoutConfig:
    """Timeout configuration for MCP tool execution."""

    timeout_ms: int = 3000  # Hard cap 3 s
    fallback_utterance: str = "Let me check on that and get back to you"


@dataclass
class MCPServerConfig:
    """Tenant-configurable MCP server connection specs."""

    server_id: UUID = field(default_factory=uuid4)
    tenant_id: UUID = field(default_factory=uuid4)
    transport: MCPTransportType = MCPTransportType.STREAMABLE_HTTP
    endpoint: str = "http://localhost:8080/mcp"
    allowed_tools: list[str] = field(default_factory=list)
    credentials_ref: str = ""


@dataclass
class MCPToolResult:
    """Result payload returned from MCP tool invocation."""

    content: str
    is_error: bool = False
    execution_time_ms: float = 0.0


class MCPHost:
    """MCP Host Client managing server connections and tool invocations."""

    def __init__(self, config: MCPServerConfig, timeout_config: ToolTimeoutConfig | None = None) -> None:
        self.config = config
        self.timeout_config = timeout_config or ToolTimeoutConfig()
        self.is_connected = False

    async def connect(self) -> bool:
        """Connect to remote MCP server."""
        self.is_connected = True
        return True

    async def list_tools(self) -> list[ToolDefinition]:
        """Fetch list of tools offered by this MCP server."""
        return [
            ToolDefinition(
                name="query_inventory",
                description="Query tenant inventory levels",
                parameters={"type": "object", "properties": {"item_id": {"type": "string"}}},
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Invoke MCP tool with 3s hard timeout bounds."""
        timeout_sec = self.timeout_config.timeout_ms / 1000.0
        try:
            return await asyncio.wait_for(self._exec_tool(name, arguments), timeout=timeout_sec)
        except asyncio.TimeoutError:
            return MCPToolResult(
                content=f"Error: Tool '{name}' timed out after {self.timeout_config.timeout_ms} ms. {self.timeout_config.fallback_utterance}",
                is_error=True,
                execution_time_ms=self.timeout_config.timeout_ms,
            )

    async def _exec_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Internal mock execution logic."""
        await asyncio.sleep(0.01)
        return MCPToolResult(content=f"Success: Executed {name} with {arguments}")
