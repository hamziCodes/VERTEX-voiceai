"""Legacy SSE transport is intentionally unavailable."""

from __future__ import annotations

from typing import Any


class MCPTransportUnavailableError(RuntimeError):
    pass


class SSEMCPTransport:
    """Fail closed until a separately tested SSE requirement exists."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    async def connect(self) -> bool:
        raise MCPTransportUnavailableError(
            "SSE MCP transport is not supported in production Phase 10."
        )

    async def list_tools(self) -> list[Any]:
        raise MCPTransportUnavailableError("SSE MCP transport is not supported.")

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        del name, arguments, idempotency_key
        raise MCPTransportUnavailableError("SSE MCP transport is not supported.")

    async def close(self) -> None:
        return None
