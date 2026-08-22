"""Phase 22: Real-Time MCP Tooling Integration Layer Test Suite."""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from core.mcp.builtin_tools import BUILTIN_TOOLS, handle_end_conversation_summary
from core.mcp.filler import ConversationalFillerSynth, FillerConfig
from core.mcp.host import MCPHost, MCPServerConfig, MCPTransportType, ToolTimeoutConfig
from core.mcp.orchestrator import ToolOrchestrator
from core.mcp.timeout_fallback import ToolTimeoutFallback
from core.mcp.transports.stdio import StdioMCPTransport

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_22_real_time_mcp_tooling_integration_layer.md"
    )
    assert plan.is_file()


def test_builtin_tools_always_present() -> None:
    names = [t.name for t in BUILTIN_TOOLS]
    assert "end_conversation_summary" in names
    assert "escalate_to_human" in names


def test_default_transport_is_http_not_stdio() -> None:
    config = MCPServerConfig(tenant_id=uuid4())
    assert config.transport == MCPTransportType.STREAMABLE_HTTP


@pytest.mark.asyncio
async def test_stdio_gated_by_env() -> None:
    stdio = StdioMCPTransport("python script.py")
    assert stdio.enabled is False
    with pytest.raises(PermissionError) as exc_info:
        await stdio.connect()
    assert "Stdio MCP transport disabled in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_host_lists_and_calls_tools() -> None:
    config = MCPServerConfig(tenant_id=uuid4())
    host = MCPHost(config)
    await host.connect()
    tools = await host.list_tools()
    assert len(tools) >= 1
    assert tools[0].name == "query_inventory"

    res = await host.call_tool("query_inventory", {"item_id": "SKU-123"})
    assert res.is_error is False
    assert "SKU-123" in res.content


@pytest.mark.asyncio
async def test_3s_timeout_triggers_fallback_and_error() -> None:
    config = MCPServerConfig(tenant_id=uuid4())
    timeout_cfg = ToolTimeoutConfig(timeout_ms=50, fallback_utterance="Checking now")
    host = MCPHost(config, timeout_config=timeout_cfg)
    await host.connect()

    # Override internal execution to sleep past timeout
    async def slow_exec(name: str, args: dict) -> any:
        await asyncio.sleep(0.2)
        return None

    host._exec_tool = slow_exec  # type: ignore

    res = await host.call_tool("slow_tool", {})
    assert res.is_error is True
    assert "timed out after 50 ms" in res.content
    assert "Checking now" in res.content


@pytest.mark.asyncio
async def test_serial_tool_orchestrator_execution() -> None:
    config = MCPServerConfig(tenant_id=uuid4())
    host = MCPHost(config)
    await host.connect()

    orchestrator = ToolOrchestrator(mcp_hosts=[host])
    tools = await orchestrator.get_all_tools()
    assert len(tools) >= 3  # 2 builtin + 1 MCP

    # Execute multiple tools serially
    res1 = await orchestrator.execute_tool_call_serially("end_conversation_summary", {"summary": "Call good"})
    assert res1["role"] == "tool"
    assert res1["data_framed"] is True

    res2 = await orchestrator.execute_tool_call_serially("query_inventory", {"item_id": "A1"})
    assert res2["role"] == "tool"
    assert res2["data_framed"] is True

    assert orchestrator.executed_tools == ["end_conversation_summary", "query_inventory"]


@pytest.mark.asyncio
async def test_conversational_filler_synth() -> None:
    triggered_phrase: list[str] = []

    cfg = FillerConfig(trigger_after_ms=50, filler_phrase="Hold on...")
    filler = ConversationalFillerSynth(
        config=cfg,
        on_filler_triggered=lambda phrase: triggered_phrase.append(phrase),
    )

    await filler.start()
    await asyncio.sleep(0.1)  # Sleep past trigger_after_ms
    assert len(triggered_phrase) == 1
    assert triggered_phrase[0] == "Hold on..."

    # Test cancellation
    filler.cancel()
    assert filler.is_active is False
