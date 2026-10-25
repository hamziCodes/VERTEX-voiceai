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
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.idempotency_keys: list[str | None] = []

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append((tool_name, arguments))
        self.idempotency_keys.append(idempotency_key)
        return {"content": f"tool:{tool_name}:{arguments.get('id', '')}"}


class _DuplicateToolLLM:
    def health_check(self) -> bool:
        return True

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        call = {
            "id": "call-1",
            "name": "delete_account",
            "arguments": {"confirmed": True},
        }
        yield LLMStreamChunk(
            tool_calls=[call, dict(call)],
            finish_reason="tool_calls",
        )


class _ContinuationLLM:
    def __init__(self) -> None:
        self.calls = 0
        self.second_messages: list[dict[str, Any]] = []

    def health_check(self) -> bool:
        return True

    async def generate_stream(self, messages, config, cancellation_token=None):
        del config, cancellation_token
        self.calls += 1
        if self.calls == 1:
            yield LLMStreamChunk(
                tool_calls=[
                    {"id": "call-42", "name": "lookup_order", "arguments": {"id": "42"}}
                ],
                finish_reason="tool_calls",
            )
            return
        self.second_messages = list(messages)
        yield LLMStreamChunk(
            text="Your order is ready for pickup.", finish_reason="stop"
        )


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_PIPELINE_V2", "tool_loop")
    monkeypatch.delenv("RUN_LIVE_PROVIDERS", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)


@pytest.mark.asyncio
async def test_streamed_tool_calls_execute_without_speaking_raw_result(
    test_env: None,
) -> None:
    audio: list[bytes] = []
    tools = _EchoTools()
    orch = PipelineOrchestrator(
        on_audio_out=lambda b: audio.append(b),
        tool_handler=tools,  # type: ignore[arg-type]
    )
    orch.llm_provider = _ToolLLM()  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id="tool-loop-1",
        tenant_id="t",
        agent_id="a",
        language="en",
    )
    reply = await orch.run_turn(config, "where is my order")
    assert tools.calls == [("lookup_order", {"id": "42"})]
    assert tools.idempotency_keys[0] is not None
    assert tools.idempotency_keys[0].startswith("tool-loop-1:")
    assert "tool:lookup_order:42" not in reply
    assert audio == []


@pytest.mark.asyncio
async def test_prefix_tool_turn_still_works(test_env: None) -> None:
    orch = PipelineOrchestrator(tool_handler=_EchoTools())  # type: ignore[arg-type]
    config = PipelineSessionConfig(
        session_id="tool-loop-2",
        tenant_id="t",
        agent_id="a",
    )
    reply = await orch.run_turn(config, "tool:lookup_order")
    assert reply == "Tool lookup_order completed."
    assert "tool:lookup_order:" not in reply


@pytest.mark.asyncio
async def test_duplicate_side_effect_tool_call_executes_once(test_env: None) -> None:
    tools = _EchoTools()
    orch = PipelineOrchestrator(tool_handler=tools)  # type: ignore[arg-type]
    orch.llm_provider = _DuplicateToolLLM()  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id="tool-loop-duplicate",
        tenant_id="t",
        agent_id="a",
    )

    await orch.run_turn(config, "delete my account")

    assert tools.calls == [("delete_account", {"confirmed": True})]


@pytest.mark.asyncio
async def test_tool_result_returns_to_llm_and_raw_output_is_never_spoken(
    test_env: None,
) -> None:
    spoken: list[str] = []
    tools = _EchoTools()
    llm = _ContinuationLLM()
    orch = PipelineOrchestrator(
        on_audio_out=lambda _audio: None,
        tool_handler=tools,  # type: ignore[arg-type]
    )
    orch.llm_provider = llm  # type: ignore[assignment]
    original = orch._synthesize_streaming

    async def _record(sentences, config, waterfall):
        spoken.extend(sentences)
        await original(sentences, config, waterfall)

    orch._synthesize_streaming = _record  # type: ignore[method-assign]
    config = PipelineSessionConfig(
        session_id="tool-continuation", tenant_id="t", agent_id="a"
    )

    reply = await orch.run_turn(config, "where is order 42")

    assert llm.calls == 2
    tool_message = next(m for m in llm.second_messages if m.get("role") == "tool")
    assert tool_message["tool_call_id"] == "call-42"
    assert reply == "Your order is ready for pickup."
    assert all("tool:lookup_order:42" not in text for text in spoken)


@pytest.mark.asyncio
async def test_tool_calls_are_capped_at_five_per_turn(test_env: None) -> None:
    class _SixCalls:
        def health_check(self) -> bool:
            return True

        async def generate_stream(self, messages, config, cancellation_token=None):
            del messages, config, cancellation_token
            yield LLMStreamChunk(
                tool_calls=[
                    {
                        "id": f"call-{index}",
                        "name": "lookup_order",
                        "arguments": {"id": str(index)},
                    }
                    for index in range(6)
                ],
                finish_reason="tool_calls",
            )

    tools = _EchoTools()
    orch = PipelineOrchestrator(tool_handler=tools)  # type: ignore[arg-type]
    orch.llm_provider = _SixCalls()  # type: ignore[assignment]
    config = PipelineSessionConfig(session_id="tool-cap", tenant_id="t", agent_id="a")
    await orch.run_turn(config, "check orders")
    assert len(tools.calls) == 5


@pytest.mark.asyncio
async def test_tool_continuation_is_capped_at_three_rounds(test_env: None) -> None:
    class _RepeatingToolLLM:
        def __init__(self) -> None:
            self.calls = 0

        def health_check(self) -> bool:
            return True

        async def generate_stream(self, messages, config, cancellation_token=None):
            del messages, config, cancellation_token
            self.calls += 1
            yield LLMStreamChunk(
                tool_calls=[
                    {
                        "id": f"round-{self.calls}",
                        "name": "lookup_order",
                        "arguments": {"id": str(self.calls)},
                    }
                ],
                finish_reason="tool_calls",
            )

    tools = _EchoTools()
    llm = _RepeatingToolLLM()
    orch = PipelineOrchestrator(tool_handler=tools)  # type: ignore[arg-type]
    orch.llm_provider = llm  # type: ignore[assignment]
    config = PipelineSessionConfig(
        session_id="tool-round-cap", tenant_id="t", agent_id="a"
    )

    await orch.run_turn(config, "keep checking")

    assert llm.calls == 4
    assert len(tools.calls) == 3
