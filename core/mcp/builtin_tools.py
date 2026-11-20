"""Validated built-in tools backed by injected session lifecycle hooks."""

from __future__ import annotations

import json
from typing import Any, Protocol

from core.providers.interfaces.llm import ToolDefinition
from post_call.models.disposition import CallDisposition


class LifecycleHooks(Protocol):
    """Runtime effects required by the built-in lifecycle tools."""

    escalation_available: bool

    async def request_end(self, *, summary: str, disposition: str) -> None: ...

    async def request_escalation(self, *, reason: str, target: str) -> None: ...


END_CONVERSATION_TOOL = ToolDefinition(
    name="end_conversation",
    description="Finish the conversation after a brief natural closing response.",
    parameters={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            "disposition": {
                "type": "string",
                "enum": [item.value for item in CallDisposition],
            },
        },
        "required": ["summary"],
    },
)

ESCALATE_TO_HUMAN_TOOL = ToolDefinition(
    name="escalate_to_human",
    description="Request the configured human handoff destination.",
    parameters={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reason": {"type": "string", "minLength": 1, "maxLength": 1000},
        },
        "required": ["reason"],
    },
)

# Compatibility catalog for the old Phase 22 contract. The production pipeline
# obtains definitions through ``available_lifecycle_tools`` and never advertises
# escalation without a real handoff hook and pinned target.
BUILTIN_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="end_conversation_summary",
        description="Legacy lifecycle summary alias",
        parameters=END_CONVERSATION_TOOL.parameters,
    ),
    ESCALATE_TO_HUMAN_TOOL,
]


def available_lifecycle_tools(
    allowed_tools: frozenset[str],
    hooks: LifecycleHooks | None,
    handoff_target: str | None,
) -> list[ToolDefinition]:
    if hooks is None:
        return []
    tools: list[ToolDefinition] = []
    if "end_conversation" in allowed_tools:
        tools.append(END_CONVERSATION_TOOL)
    if (
        "escalate_to_human" in allowed_tools
        and hooks.escalation_available
        and handoff_target
    ):
        tools.append(ESCALATE_TO_HUMAN_TOOL)
    return tools


def validate_end_arguments(arguments: dict[str, Any]) -> tuple[str, str]:
    if set(arguments) - {"summary", "disposition"}:
        raise ValueError("Unexpected end-conversation argument.")
    summary = arguments.get("summary")
    disposition = arguments.get("disposition", CallDisposition.COMPLETED.value)
    if not isinstance(summary, str) or not 1 <= len(summary.strip()) <= 2_000:
        raise ValueError("Summary must contain between 1 and 2000 characters.")
    if not isinstance(disposition, str) or disposition not in {
        item.value for item in CallDisposition
    }:
        raise ValueError("Disposition is invalid.")
    return summary.strip(), disposition


def validate_escalation_arguments(arguments: dict[str, Any]) -> str:
    if set(arguments) - {"reason"}:
        raise ValueError("Unexpected escalation argument.")
    reason = arguments.get("reason")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 1_000:
        raise ValueError(
            "Escalation reason must contain between 1 and 1000 characters."
        )
    return reason.strip()


async def handle_end_conversation_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    """Legacy non-runtime helper retained for the Phase 22 compatibility test."""
    summary, disposition = validate_end_arguments(arguments)
    return {
        "status": "legacy_summary_only",
        "summary": summary,
        "disposition": disposition,
    }


async def handle_escalate_to_human(arguments: dict[str, Any]) -> dict[str, Any]:
    """Legacy helper fails closed because it has no transport handoff hook."""
    reason = validate_escalation_arguments(arguments)
    return {"status": "unavailable", "reason": reason}


def lifecycle_result_content(status: str) -> str:
    return json.dumps({"status": status}, separators=(",", ":"))
