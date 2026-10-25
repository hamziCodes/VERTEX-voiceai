"""Phase 22: Real-Time MCP Tooling Integration Layer Test Suite."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from core.mcp.builtin_tools import BUILTIN_TOOLS
from core.mcp.filler import ConversationalFillerSynth, FillerConfig
from core.mcp.host import MCPHost, MCPServerConfig, MCPTransportType, ToolTimeoutConfig
from core.mcp.orchestrator import ToolOrchestrator
from core.mcp.transports.stdio import StdioMCPTransport
from core.providers.interfaces.llm import ToolDefinition

REPO_ROOT = Path(__file__).resolve().parents[3]


class _FakeMCPTransport:
    async def connect(self) -> bool:
        return True

    async def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="query_inventory",
                description="Query inventory",
                parameters={
                    "type": "object",
                    "properties": {"item_id": {"type": "string"}},
                    "required": ["item_id"],
                },
            )
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        del name, idempotency_key
        return SimpleNamespace(
            content=f"inventory:{arguments['item_id']}", is_error=False
        )

    async def close(self) -> None:
        return None


def _enabled_config() -> MCPServerConfig:
    return MCPServerConfig(
        tenant_id=uuid4(),
        enabled=True,
        allowed_tools=("query_inventory",),
    )


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
    stdio = StdioMCPTransport(
        "python", ("script.py",), allowed_executables=frozenset({"python"})
    )
    assert stdio.enabled is False
    with pytest.raises(PermissionError) as exc_info:
        await stdio.connect()
    assert "disabled" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_host_lists_and_calls_tools() -> None:
    config = _enabled_config()
    host = MCPHost(config, transport=_FakeMCPTransport())
    await host.connect()
    tools = await host.list_tools()
    assert len(tools) >= 1
    assert tools[0].name == "query_inventory"

    res = await host.call_tool("query_inventory", {"item_id": "SKU-123"})
    assert res.is_error is False
    assert "SKU-123" in res.content


@pytest.mark.asyncio
async def test_3s_timeout_triggers_fallback_and_error() -> None:
    config = _enabled_config()
    timeout_cfg = ToolTimeoutConfig(timeout_ms=50, fallback_utterance="Checking now")
    host = MCPHost(config, timeout_config=timeout_cfg, transport=_FakeMCPTransport())
    await host.connect()

    # Override internal execution to sleep past timeout
    async def slow_exec(
        name: str,
        args: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Any:
        del name, args, idempotency_key
        await asyncio.sleep(0.2)
        return None

    host._exec_tool = slow_exec  # type: ignore

    res = await host.call_tool("query_inventory", {"item_id": "slow"})
    assert res.is_error is True
    assert "timed out after 50 ms" in res.content
    assert "Checking now" in res.content


@pytest.mark.asyncio
async def test_serial_tool_orchestrator_execution() -> None:
    config = _enabled_config()
    host = MCPHost(config, transport=_FakeMCPTransport())
    await host.connect()

    orchestrator = ToolOrchestrator(mcp_hosts=[host])
    tools = await orchestrator.get_all_tools()
    assert len(tools) >= 3  # 2 builtin + 1 MCP

    # Execute multiple tools serially
    res1 = await orchestrator.execute_tool_call_serially(
        "end_conversation_summary", {"summary": "Call good"}
    )
    assert res1["role"] == "tool"
    assert res1["data_framed"] is True

    res2 = await orchestrator.execute_tool_call_serially(
        "query_inventory", {"item_id": "A1"}
    )
    assert res2["role"] == "tool"
    assert res2["data_framed"] is True

    assert orchestrator.executed_tools == [
        "end_conversation_summary",
        "query_inventory",
    ]


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
