"""Tool Timeout Fallback Handler — Enqueues spoken fallback utterance on 3s timeout."""

from __future__ import annotations

from core.mcp.host import ToolTimeoutConfig


class ToolTimeoutFallback:
    """Handles timeout fallback utterance generation for long-running tools."""

    def __init__(self, config: ToolTimeoutConfig | None = None) -> None:
        self.config = config or ToolTimeoutConfig()

    def get_fallback_result(self, tool_name: str) -> dict[str, str]:
        """Return structured fallback response for LLM & spoken utterance for TTS."""
        return {
            "error": f"Tool '{tool_name}' timed out after {self.config.timeout_ms} ms",
            "spoken_fallback": self.config.fallback_utterance,
        }
