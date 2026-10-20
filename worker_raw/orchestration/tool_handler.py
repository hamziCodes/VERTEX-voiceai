"""Worker Pipeline Tool Handler — Bridges LLM tool_call events into ToolOrchestrator."""

from __future__ import annotations

from typing import Any

from core.mcp.orchestrator import ToolOrchestrator


class PipelineToolHandler:
    """Worker-raw integration hook for real-time tool calls."""

    def __init__(self, orchestrator: ToolOrchestrator | None = None) -> None:
        self.orchestrator = orchestrator or ToolOrchestrator()
        self._allowed_tools: frozenset[str] | None = None

    def set_allowed_tools(self, tool_names: tuple[str, ...]) -> None:
        """Install the published per-session tool allowlist."""

        self._allowed_tools = frozenset(tool_names)

    async def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute tool call serially and return DATA-framed turn result."""
        if self._allowed_tools is not None and tool_name not in self._allowed_tools:
            return {
                "role": "tool",
                "name": tool_name,
                "content": f"Error: Tool '{tool_name}' is not enabled for this agent.",
                "is_error": True,
                "data_framed": True,
            }
        return await self.orchestrator.execute_tool_call_serially(tool_name, arguments)
