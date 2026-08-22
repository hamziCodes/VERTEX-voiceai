"""Server-Sent Events (SSE) MCP Transport."""

from __future__ import annotations


class SSEMCPTransport:
    """Default cloud SSE MCP transport."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint

    async def connect(self) -> bool:
        return True
