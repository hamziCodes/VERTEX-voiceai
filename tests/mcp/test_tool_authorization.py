from __future__ import annotations

import asyncio

import pytest

from worker_raw.orchestration.tool_handler import (
    PipelineToolHandler,
    ToolExecutionLimits,
)


class _Delegate:
    async def execute_tool_call_serially(self, name, arguments):
        return {"role": "tool", "name": name, "content": "ok", "is_error": False}


@pytest.mark.asyncio
async def test_unlisted_tool_is_rejected_before_delegate() -> None:
    handler = PipelineToolHandler(_Delegate())  # type: ignore[arg-type]
    handler.configure_session(allowed_tools=("allowed",))
    result = await handler.handle_tool_call("forbidden", {})
    assert result["error_code"] == "tool_not_allowed"


@pytest.mark.asyncio
async def test_oversized_arguments_are_rejected() -> None:
    handler = PipelineToolHandler(_Delegate())  # type: ignore[arg-type]
    handler.configure_session(allowed_tools=("allowed",))
    result = await handler.handle_tool_call("allowed", {"value": "x" * 9_000})
    assert result["error_code"] == "tool_arguments_too_large"


@pytest.mark.asyncio
async def test_tool_timeout_is_typed_and_cancels_delegate() -> None:
    cancelled = asyncio.Event()

    class _Slow:
        async def execute_tool_call_serially(self, name, arguments):
            del name, arguments
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    handler = PipelineToolHandler(
        _Slow(),
        limits=ToolExecutionLimits(timeout_ms=10),  # type: ignore[arg-type]
    )
    handler.configure_session(allowed_tools=("slow",))
    result = await handler.handle_tool_call("slow", {})
    assert result["error_code"] == "tool_timeout"
    await asyncio.wait_for(cancelled.wait(), timeout=0.2)


@pytest.mark.asyncio
async def test_lifecycle_hook_timeout_is_typed_and_cancelled() -> None:
    cancelled = asyncio.Event()

    class _SlowLifecycle:
        escalation_available = False

        async def request_end(self, *, summary: str, disposition: str) -> None:
            del summary, disposition
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def request_escalation(self, *, reason: str, target: str) -> None:
            del reason, target

    handler = PipelineToolHandler(limits=ToolExecutionLimits(timeout_ms=10))
    handler.configure_session(
        allowed_tools=("end_conversation",), lifecycle_hooks=_SlowLifecycle()
    )
    result = await handler.handle_tool_call(
        "end_conversation", {"summary": "Resolved"}
    )
    assert result["error_code"] == "tool_timeout"
    await asyncio.wait_for(cancelled.wait(), timeout=0.2)


@pytest.mark.asyncio
async def test_caller_cancellation_reaches_tool_delegate() -> None:
    cancelled = asyncio.Event()

    class _Slow:
        async def execute_tool_call_serially(self, name, arguments):
            del name, arguments
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    handler = PipelineToolHandler(_Slow())  # type: ignore[arg-type]
    handler.configure_session(allowed_tools=("slow",))
    task = asyncio.create_task(handler.handle_tool_call("slow", {}))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), timeout=0.2)


@pytest.mark.asyncio
async def test_tool_result_is_bounded_before_llm_continuation() -> None:
    class _Large:
        async def execute_tool_call_serially(self, name, arguments):
            del arguments
            return {"role": "tool", "name": name, "content": "x" * 30_000}

    handler = PipelineToolHandler(_Large())  # type: ignore[arg-type]
    handler.configure_session(allowed_tools=("large",))
    result = await handler.handle_tool_call("large", {})
    assert len(result["content"].encode("utf-8")) <= 16 * 1024
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_tool_failure_does_not_expose_arguments_or_exception_details(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_marker = "private-customer-value"

    class _Failing:
        async def execute_tool_call_serially(self, name, arguments):
            del name, arguments
            raise RuntimeError(f"provider failure containing {secret_marker}")

    handler = PipelineToolHandler(_Failing())  # type: ignore[arg-type]
    handler.configure_session(allowed_tools=("lookup",))

    result = await handler.handle_tool_call("lookup", {"query": secret_marker})

    assert result["error_code"] == "tool_execution_failed"
    assert secret_marker not in result["content"]
    assert secret_marker not in caplog.text
