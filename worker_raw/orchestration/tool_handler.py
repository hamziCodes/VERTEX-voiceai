"""Worker Pipeline Tool Handler — Bridges LLM tool_call events into ToolOrchestrator."""

from __future__ import annotations

from typing import Any

from core.mcp.orchestrator import ToolOrchestrator


class PipelineToolHandler:
    """Worker-raw integration hook for real-time tool calls."""

    def __init__(self, orchestrator: ToolOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or ToolOrchestrator()

    async def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute tool call serially and return DATA-framed turn result."""
        return await self.orchestrator.execute_tool_call_serially(tool_name, arguments)
