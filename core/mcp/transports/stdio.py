"""Stdio MCP Transport — Local dev only, gated by UCVE_MCP_ALLOW_STDIO env var."""

from __future__ import annotations

import os


class StdioMCPTransport:
    """Local subprocess stdio transport for local development."""

    def __init__(self, command: str) -> None:
        self.command = command
        self.enabled = os.getenv("UCVE_MCP_ALLOW_STDIO", "false").lower() == "true"

    async def connect(self) -> bool:
        if not self.enabled:
            raise PermissionError("Stdio MCP transport disabled in production. Set UCVE_MCP_ALLOW_STDIO=true for local dev.")
        return True
