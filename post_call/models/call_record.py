"""Canonical CallRecord Data Model — Pydantic v2 post-call record schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.memory_embed import MemoryEmbedStatus
from post_call.models.recording import CallRecording


class CallRecord(BaseModel):
    """Canonical CallRecord representation stored after session completion."""

    call_id: UUID = Field(default_factory=uuid4, description="Primary unique call ID")
    tenant_id: UUID = Field(..., description="Owning tenant UUID")
    agent_id: UUID = Field(..., description="Agent UUID")
    session_id: UUID = Field(..., description="FSM Session UUID")
    caller_id: str | None = Field(default=None, description="E.164 caller phone number if telephony-origin")
    started_at: datetime = Field(..., description="Call start timestamp")
    ended_at: datetime = Field(..., description="Call end timestamp")
    end_reason: str = Field(default="user_hangup", description="Session teardown reason")
    transport_type: str = Field(default="websocket", description="websocket / sip")
    disposition: CallDisposition = Field(default=CallDisposition.COMPLETED)
    turns: list[DiarizedTurn] = Field(default_factory=list, description="Diarized speech turns")
    recording: CallRecording | None = Field(default=None, description="Audio recording metadata")
    transcript_redacted_ref: str = Field(default="", description="Ref/URI to redacted transcript JSONB")
    transcript_raw_ref: str = Field(default="", description="Ref/URI to raw encrypted transcript")
    compliance_tier: str = Field(default="standard", description="standard / hipaa / gdpr_strict")
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict, description="Metrics & telemetry snapshot")
    memory_embed_status: MemoryEmbedStatus = Field(default=MemoryEmbedStatus.PENDING)
