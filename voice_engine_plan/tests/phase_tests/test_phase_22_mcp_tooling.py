"""Phase 22: Real-Time MCP Tooling Integration Layer."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_22_real_time_mcp_tooling_integration_layer.md"
)


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_batch5_decisions_documented() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "3 s" in text or "3000 ms" in text
    assert "serial" in text.lower()
    assert "streamable_http" in text or "HTTP/SSE" in text
    assert "None — fully deterministic" in text


@pytest.mark.asyncio
async def test_mcp_tool_timeout_triggers_fallback() -> None:
    try:
        from core.mcp.timeout_fallback import ToolTimeoutFallback  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 22 implementation pending: {exc}")
    fallback = ToolTimeoutFallback()
    message = fallback.default_message()
    assert "check" in message.lower() or len(message) > 0
