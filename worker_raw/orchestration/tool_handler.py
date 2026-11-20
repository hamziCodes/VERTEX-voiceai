"""Bounded bridge from model tool calls to authorized runtime effects."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any

from core.mcp.builtin_tools import (
    LifecycleHooks,
    available_lifecycle_tools,
    lifecycle_result_content,
    validate_end_arguments,
    validate_escalation_arguments,
)
from core.mcp.orchestrator import ToolOrchestrator
from core.providers.interfaces.llm import ToolDefinition


@dataclass(frozen=True, slots=True)
class ToolExecutionLimits:
    timeout_ms: int = 3_000
    max_argument_bytes: int = 8 * 1024
    max_result_bytes: int = 16 * 1024

    def __post_init__(self) -> None:
        if not 1 <= self.timeout_ms <= 3_000:
            raise ValueError("Tool timeout must be between 1 and 3000 ms.")
        if self.max_argument_bytes < 256 or self.max_result_bytes < 256:
            raise ValueError("Tool payload limits are too small.")


class PipelineToolHandler:
    """Authorize, validate, execute, and bound one model-requested tool call."""

    def __init__(
        self,
        orchestrator: ToolOrchestrator | Any | None = None,
        *,
        limits: ToolExecutionLimits | None = None,
    ) -> None:
        self.orchestrator = orchestrator or ToolOrchestrator()
        self.limits = limits or ToolExecutionLimits()
        self._allowed_tools: frozenset[str] = frozenset()
        self._lifecycle_hooks: LifecycleHooks | None = None
        self._handoff_target: str | None = None

    def set_allowed_tools(self, tool_names: tuple[str, ...]) -> None:
        self._allowed_tools = frozenset(tool_names)

    def configure_session(
        self,
        *,
        allowed_tools: tuple[str, ...],
        lifecycle_hooks: LifecycleHooks | None = None,
        handoff_target: str | None = None,
    ) -> None:
        self._allowed_tools = frozenset(allowed_tools)
        self._lifecycle_hooks = lifecycle_hooks
        self._handoff_target = handoff_target.strip() if handoff_target else None

    def available_tools(self) -> list[ToolDefinition]:
        return available_lifecycle_tools(
            self._allowed_tools, self._lifecycle_hooks, self._handoff_target
        )

    async def prepare_tools(self) -> list[ToolDefinition]:
        tools = self.available_tools()
        external_loader = getattr(self.orchestrator, "get_external_tools", None)
        if not callable(external_loader):
            return tools
        reserved = {
            "end_conversation",
            "end_conversation_summary",
            "escalate_to_human",
        }
        external = await external_loader()
        tools.extend(
            tool
            for tool in external
            if tool.name in self._allowed_tools and tool.name not in reserved
        )
        if len({tool.name for tool in tools}) != len(tools):
            raise ValueError("Tool inventory contains duplicate names.")
        return tools

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if tool_name not in self._allowed_tools:
            return _tool_error(tool_name, "tool_not_allowed")
        try:
            argument_bytes = len(
                json.dumps(arguments, separators=(",", ":"), ensure_ascii=False).encode(
                    "utf-8"
                )
            )
        except (TypeError, ValueError):
            return _tool_error(tool_name, "invalid_arguments")
        if argument_bytes > self.limits.max_argument_bytes:
            return _tool_error(tool_name, "tool_arguments_too_large")

        if tool_name in {"end_conversation", "end_conversation_summary"}:
            return await self._run_lifecycle_call(
                tool_name, self._end_conversation(tool_name, arguments)
            )
        if tool_name == "escalate_to_human":
            return await self._run_lifecycle_call(tool_name, self._escalate(arguments))

        try:
            execute = self.orchestrator.execute_tool_call_serially
            if idempotency_key is None:
                operation = execute(tool_name, arguments)
            else:
                operation = execute(
                    tool_name, arguments, idempotency_key=idempotency_key
                )
            result = await asyncio.wait_for(
                operation,
                timeout=self.limits.timeout_ms / 1000.0,
            )
        except TimeoutError:
            return _tool_error(tool_name, "tool_timeout")
        except asyncio.CancelledError:
            raise
        except Exception:
            return _tool_error(tool_name, "tool_execution_failed")
        return self._bound_result(tool_name, result)

    async def close(self) -> None:
        closer = getattr(self.orchestrator, "close", None)
        if callable(closer):
            await closer()

    async def _run_lifecycle_call(
        self, tool_name: str, operation: Awaitable[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                operation, timeout=self.limits.timeout_ms / 1000.0
            )
        except TimeoutError:
            return _tool_error(tool_name, "tool_timeout")
        except asyncio.CancelledError:
            raise
        except Exception:
            return _tool_error(tool_name, "tool_execution_failed")

    async def _end_conversation(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if self._lifecycle_hooks is None:
            return _tool_error(tool_name, "tool_unavailable")
        try:
            summary, disposition = validate_end_arguments(arguments)
        except ValueError:
            return _tool_error(tool_name, "invalid_arguments")
        await self._lifecycle_hooks.request_end(
            summary=summary, disposition=disposition
        )
        return {
            "role": "tool",
            "name": tool_name,
            "content": lifecycle_result_content("end_requested"),
            "is_error": False,
            "data_framed": True,
            "lifecycle_action": "end_conversation",
        }

    async def _escalate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if (
            self._lifecycle_hooks is None
            or not self._lifecycle_hooks.escalation_available
            or not self._handoff_target
        ):
            return _tool_error("escalate_to_human", "tool_unavailable")
        try:
            reason = validate_escalation_arguments(arguments)
        except ValueError:
            return _tool_error("escalate_to_human", "invalid_arguments")
        await self._lifecycle_hooks.request_escalation(
            reason=reason, target=self._handoff_target
        )
        return {
            "role": "tool",
            "name": "escalate_to_human",
            "content": lifecycle_result_content("handoff_requested"),
            "is_error": False,
            "data_framed": True,
            "lifecycle_action": "escalate_to_human",
        }

    def _bound_result(self, tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
        content = str(result.get("content", ""))
        raw = content.encode("utf-8")
        truncated = len(raw) > self.limits.max_result_bytes
        if truncated:
            raw = raw[: self.limits.max_result_bytes]
            content = raw.decode("utf-8", errors="ignore")
        return {
            **result,
            "role": "tool",
            "name": tool_name,
            "content": content,
            "is_error": bool(result.get("is_error", False)),
            "data_framed": True,
            "truncated": truncated,
        }


def _tool_error(name: str, code: str) -> dict[str, Any]:
    messages = {
        "tool_not_allowed": "Tool is not enabled for this agent.",
        "tool_unavailable": "Tool is unavailable for this session.",
        "invalid_arguments": "Tool arguments are invalid.",
        "tool_arguments_too_large": "Tool arguments exceed the size limit.",
        "tool_timeout": "Tool execution timed out.",
        "tool_execution_failed": "Tool execution failed.",
    }
    return {
        "role": "tool",
        "name": name,
        "content": json.dumps(
            {"error": code, "message": messages.get(code, "Tool failed.")},
            separators=(",", ":"),
        ),
        "is_error": True,
        "error_code": code,
        "data_framed": True,
        "truncated": False,
    }
