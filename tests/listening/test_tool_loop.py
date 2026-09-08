"""Phase 7 — LLM tool-call loop wiring on PipelineOrchestrator."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import LLMConfig, LLMStreamChunk
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class _ToolLLM:
    def health_check(self) -> bool:
        return True

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        yield LLMStreamChunk(
            tool_calls=[{"name": "lookup_order", "arguments": {"id": "42"}}],
            finish_reason="tool_calls",
        )


class _EchoTools:
    async def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"content": f"tool:{tool_name}:{arguments.get('id', '')}"}


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_PIPELINE_V2", "tool_loop")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


@pytest.mark.asyncio
async def test_streamed_tool_calls_execute_and_speak(test_env: None) -> None:
    audio: list[bytes] = []
    orch = PipelineOrchestrator(
        on_audio_out=lambda b: audio.append(b),
        tool_handler=_EchoTools(),  # type: ignore[arg-type]
    )
    orch.llm_provider = _ToolLLM()  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id="tool-loop-1",
        tenant_id="t",
        agent_id="a",
        language="en",
    )
    reply = await orch.run_turn(config, "where is my order")
    assert "lookup_order" in reply
    assert audio, "tool result should be spoken via TTS"


@pytest.mark.asyncio
async def test_prefix_tool_turn_still_works(test_env: None) -> None:
    orch = PipelineOrchestrator(tool_handler=_EchoTools())  # type: ignore[arg-type]
    config = PipelineSessionConfig(
        session_id="tool-loop-2",
        tenant_id="t",
        agent_id="a",
    )
    reply = await orch.run_turn(config, "tool:lookup_order")
    assert "lookup_order" in reply
