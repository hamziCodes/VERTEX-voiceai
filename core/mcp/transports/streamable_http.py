"""Streamable HTTP MCP Transport — Primary cloud multi-tenant transport."""

from __future__ import annotations


class StreamableHTTPMCPTransport:
    """Primary HTTP/JSON-RPC MCP transport for cloud multi-tenant deployment."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    async def connect(self) -> bool:
        return True
