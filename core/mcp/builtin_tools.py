"""Built-in Session Lifecycle Tools — Always-available default tools (end_conversation_summary, escalate_to_human)."""

from __future__ import annotations

import asyncio
from typing import Any

from core.providers.interfaces.llm import ToolDefinition


def _sync_end_conversation_summary(summary: str, disposition: str) -> dict[str, Any]:
    """Sync helper executed via asyncio.to_thread to prevent event loop blocking."""
    return {"status": "disposition_set", "disposition": disposition, "summary": summary}


def _sync_escalate_to_human(reason: str, department: str) -> dict[str, Any]:
    """Sync helper executed via asyncio.to_thread for warm transfer."""
    return {"status": "escalation_queued", "reason": reason, "department": department}


async def handle_end_conversation_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    """Async wrapper using asyncio.to_thread for non-blocking execution."""
    summary = arguments.get("summary", "")
    disposition = arguments.get("disposition", "completed")
    return await asyncio.to_thread(_sync_end_conversation_summary, summary, disposition)


async def handle_escalate_to_human(arguments: dict[str, Any]) -> dict[str, Any]:
    """Async wrapper using asyncio.to_thread for non-blocking execution."""
    reason = arguments.get("reason", "customer_request")
    department = arguments.get("department", "support")
    return await asyncio.to_thread(_sync_escalate_to_human, reason, department)


BUILTIN_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="end_conversation_summary",
        description="End session and record call summary and disposition",
        parameters={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Call summary"},
                "disposition": {"type": "string", "description": "Call disposition"},
            },
            "required": ["summary"],
        },
    ),
    ToolDefinition(
        name="escalate_to_human",
        description="Escalate call to human agent / warm transfer",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for escalation"},
                "department": {"type": "string", "description": "Target department"},
            },
            "required": ["reason"],
        },
    ),
]
