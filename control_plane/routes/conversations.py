"""Tenant-scoped conversation history and post-call intelligence APIs."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from core.db.repos.post_call_repo import PostCallNotFoundError
from post_call.models.call_record import CallRecord
from post_call.models.recording import RecordingState

router = APIRouter(prefix="/v1/conversations", tags=["conversations"])
ConversationReader = Annotated[
    AuthContext, Depends(require_permission("conversation:read"))
]


def _tenant_id(auth: AuthContext) -> UUID:
    try:
        return UUID(auth.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid tenant identifier."
        ) from exc


def _repositories(request: Request) -> tuple[Any, Any]:
    calls = getattr(request.app.state, "post_call_repository", None)
    jobs = getattr(request.app.state, "post_call_job_repository", None)
    if calls is None or jobs is None:
        raise HTTPException(status_code=503, detail="Conversation history unavailable.")
    return calls, jobs


def _encode_cursor(record: CallRecord) -> str:
    payload = json.dumps(
        [record.started_at.isoformat(), str(record.call_id)], separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(value: str | None) -> tuple[datetime, UUID] | None:
    if value is None:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        timestamp, call_id = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(timestamp), UUID(call_id)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=422, detail="Invalid conversation cursor."
        ) from exc


def _summary(record: CallRecord) -> dict[str, Any]:
    return {
        "call_id": str(record.call_id),
        "agent_id": str(record.agent_id),
        "started_at": record.started_at.isoformat(),
        "ended_at": record.ended_at.isoformat() if record.ended_at else None,
        "transport_type": record.transport_type,
        "disposition": record.disposition.value,
        "recording_state": record.recording_state.value,
        "turn_count": len(record.turns),
    }


def _recording_view(record: CallRecord) -> dict[str, Any]:
    if record.recording_state is RecordingState.AVAILABLE and record.recording:
        return {
            "state": "available",
            "duration_sec": record.recording.duration_sec,
            "access": "gated",
        }
    if record.recording_state is RecordingState.FAILED:
        return {
            "state": "failed",
            "error_code": record.recording_error_code,
            "access": "unavailable",
        }
    return {"state": record.recording_state.value, "access": "unavailable"}


@router.get("")
async def list_conversations(
    request: Request,
    auth: ConversationReader,
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=1024),
) -> dict[str, Any]:
    calls, _ = _repositories(request)
    records = await calls.list_calls(
        _tenant_id(auth), before=_decode_cursor(cursor), limit=limit + 1
    )
    visible = records[:limit]
    return {
        "items": [_summary(record) for record in visible],
        "next_cursor": _encode_cursor(visible[-1]) if len(records) > limit else None,
    }


@router.get("/{call_id}")
async def get_conversation(
    call_id: UUID, request: Request, auth: ConversationReader
) -> dict[str, Any]:
    calls, _ = _repositories(request)
    try:
        record = await calls.get_call_by_id(_tenant_id(auth), call_id)
    except PostCallNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **_summary(record),
        "end_reason": record.end_reason,
        "transcript": [turn.model_dump(mode="json") for turn in record.turns],
        "usage": dict(record.usage_snapshot),
        "recording": _recording_view(record),
    }


@router.get("/{call_id}/intelligence")
async def get_conversation_intelligence(
    call_id: UUID, request: Request, auth: ConversationReader
) -> dict[str, Any]:
    calls, jobs = _repositories(request)
    tenant_id = _tenant_id(auth)
    try:
        await calls.get_call_by_id(tenant_id, call_id)
    except PostCallNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = await jobs.get_result(tenant_id, call_id)
    if result is None:
        return {"state": "unavailable", "result": None, "review": None}
    review = await jobs.get_review_for_result(tenant_id, result.result_id)
    return {
        "state": "available",
        "result": result.model_dump(
            mode="json", exclude={"provider_snapshot", "tenant_id"}
        ),
        "review": review.model_dump(mode="json", exclude={"tenant_id"})
        if review
        else None,
    }
