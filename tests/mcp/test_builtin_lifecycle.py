from __future__ import annotations

from typing import Any

import pytest

from core.fsm.states import SessionState
from core.mcp.builtin_tools import LifecycleHooks
from core.providers.interfaces.llm import LLMStreamChunk
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.orchestration.tool_handler import PipelineToolHandler


class _Lifecycle(LifecycleHooks):
    def __init__(self, *, escalation_available: bool = False) -> None:
        self.escalation_available = escalation_available
        self.ends: list[tuple[str, str]] = []
        self.escalations: list[tuple[str, str]] = []

    async def request_end(self, *, summary: str, disposition: str) -> None:
        self.ends.append((summary, disposition))

    async def request_escalation(self, *, reason: str, target: str) -> None:
        self.escalations.append((reason, target))


@pytest.mark.asyncio
async def test_end_conversation_calls_real_hook_with_validated_data() -> None:
    hooks = _Lifecycle()
    handler = PipelineToolHandler()
    handler.configure_session(
        allowed_tools=("end_conversation",), lifecycle_hooks=hooks
    )

    result = await handler.handle_tool_call(
        "end_conversation",
        {"summary": "Customer question resolved.", "disposition": "completed"},
    )

    assert result["is_error"] is False
    assert result["lifecycle_action"] == "end_conversation"
    assert hooks.ends == [("Customer question resolved.", "completed")]


@pytest.mark.asyncio
async def test_escalation_is_unavailable_without_real_handoff_hook() -> None:
    hooks = _Lifecycle(escalation_available=False)
    handler = PipelineToolHandler()
    handler.configure_session(
        allowed_tools=("end_conversation", "escalate_to_human"),
        lifecycle_hooks=hooks,
        handoff_target="support-queue",
    )

    assert [tool.name for tool in handler.available_tools()] == ["end_conversation"]
    result = await handler.handle_tool_call(
        "escalate_to_human", {"reason": "Customer requested a person"}
    )
    assert result["is_error"] is True
    assert result["error_code"] == "tool_unavailable"
    assert hooks.escalations == []


@pytest.mark.asyncio
async def test_configured_escalation_uses_pinned_target() -> None:
    hooks = _Lifecycle(escalation_available=True)
    handler = PipelineToolHandler()
    handler.configure_session(
        allowed_tools=("escalate_to_human",),
        lifecycle_hooks=hooks,
        handoff_target="billing-queue",
    )

    assert [tool.name for tool in handler.available_tools()] == ["escalate_to_human"]
    result = await handler.handle_tool_call(
        "escalate_to_human",
        {"reason": "Billing dispute"},
    )
    assert result["is_error"] is False
    assert hooks.escalations == [("Billing dispute", "billing-queue")]


@pytest.mark.asyncio
async def test_model_cannot_override_pinned_handoff_target() -> None:
    hooks = _Lifecycle(escalation_available=True)
    handler = PipelineToolHandler()
    handler.configure_session(
        allowed_tools=("escalate_to_human",),
        lifecycle_hooks=hooks,
        handoff_target="billing-queue",
    )

    result = await handler.handle_tool_call(
        "escalate_to_human",
        {"reason": "Billing dispute", "target": "attacker-controlled-target"},
    )

    assert result["error_code"] == "invalid_arguments"
    assert hooks.escalations == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "error_code"),
    [
        ({}, "invalid_arguments"),
        ({"summary": "x", "disposition": "invented"}, "invalid_arguments"),
        ({"summary": "x" * 2_001}, "invalid_arguments"),
    ],
)
async def test_lifecycle_arguments_fail_closed(
    arguments: dict[str, Any], error_code: str
) -> None:
    handler = PipelineToolHandler()
    handler.configure_session(
        allowed_tools=("end_conversation",), lifecycle_hooks=_Lifecycle()
    )
    result = await handler.handle_tool_call("end_conversation", arguments)
    assert result["is_error"] is True
    assert result["error_code"] == error_code


@pytest.mark.asyncio
async def test_pipeline_speaks_closing_then_ends_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_PIPELINE_V2", "tool_loop")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")

    class _EndLLM:
        def __init__(self) -> None:
            self.calls = 0
            self.tools = []

        def health_check(self) -> bool:
            return True

        async def generate_stream(self, messages, config, cancellation_token=None):
            del messages, cancellation_token
            self.calls += 1
            self.tools = config.tools
            if self.calls == 1:
                yield LLMStreamChunk(
                    tool_calls=[
                        {
                            "id": "end-1",
                            "name": "end_conversation",
                            "arguments": {
                                "summary": "Question resolved",
                                "disposition": "information_provided",
                            },
                        }
                    ],
                    finish_reason="tool_calls",
                )
                return
            yield LLMStreamChunk(
                text="Thank you for calling. Goodbye.", finish_reason="stop"
            )

    llm = _EndLLM()
    orchestrator = PipelineOrchestrator()
    orchestrator.llm_provider = llm  # type: ignore[assignment]

    class _Transport:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict[str, str]]] = []

        async def send_control_event(self, name, data) -> None:
            self.events.append((name, data))

    class _Session:
        def __init__(self) -> None:
            self.transport = _Transport()
            self.stop_reasons: list[str] = []

        async def request_graceful_stop(self, reason: str) -> None:
            self.stop_reasons.append(reason)

    session = _Session()
    orchestrator.attach_ws_session(session)
    config = PipelineSessionConfig(
        session_id="lifecycle-end",
        tenant_id="tenant",
        agent_id="agent",
        tool_allowlist=("end_conversation",),
    )

    reply = await orchestrator.run_turn(config, "That answers my question")

    assert reply == "Thank you for calling. Goodbye."
    assert [tool.name for tool in llm.tools] == ["end_conversation"]
    assert orchestrator._session_disposition == "information_provided"
    assert orchestrator.fsm.state is SessionState.DISCONNECTED
    assert orchestrator._lifecycle_completed is True
    assert session.stop_reasons == ["agent_end_conversation"]
    session_ending = [
        event for event in session.transport.events if event[0] == "session.ending"
    ]
    assert session_ending == [(
        "session.ending",
        {"reason": "agent_end_conversation"},
    )]
