"""Canonical CallRecord Data Model — Pydantic v2 post-call record schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.memory_embed import MemoryEmbedStatus
from post_call.models.recording import CallRecording, RecordingState


class CallRecord(BaseModel):
    """Canonical CallRecord representation stored after session completion."""

    call_id: UUID = Field(default_factory=uuid4, description="Primary unique call ID")
    tenant_id: UUID = Field(..., description="Owning tenant UUID")
    agent_id: UUID = Field(..., description="Agent UUID")
    session_id: UUID = Field(..., description="FSM Session UUID")
    caller_id: str | None = Field(
        default=None, description="E.164 caller phone number if telephony-origin"
    )
    started_at: datetime = Field(..., description="Call start timestamp")
    ended_at: datetime | None = Field(default=None, description="Call end timestamp")
    end_reason: str = Field(
        default="user_hangup", description="Session teardown reason"
    )
    transport_type: str = Field(default="websocket", description="websocket / sip")
    disposition: CallDisposition = Field(default=CallDisposition.COMPLETED)
    turns: list[DiarizedTurn] = Field(
        default_factory=list, description="Diarized speech turns"
    )
    recording: CallRecording | None = Field(
        default=None, description="Audio recording metadata"
    )
    recording_state: RecordingState = Field(default=RecordingState.NOT_REQUESTED)
    recording_error_code: str | None = Field(default=None, max_length=64)
    policy_snapshot: dict[str, Any] = Field(default_factory=dict)
    provider_snapshot: dict[str, Any] = Field(default_factory=dict)
    usage_snapshot: dict[str, Any] = Field(default_factory=dict)
    transcript_redacted_ref: str = Field(
        default="", description="Ref/URI to redacted transcript JSONB"
    )
    transcript_raw_ref: str = Field(
        default="", description="Ref/URI to raw encrypted transcript"
    )
    compliance_tier: str = Field(
        default="standard", description="standard / hipaa / gdpr_strict"
    )
    metrics_snapshot: dict[str, Any] = Field(
        default_factory=dict, description="Metrics & telemetry snapshot"
    )
    memory_embed_status: MemoryEmbedStatus = Field(default=MemoryEmbedStatus.PENDING)

    @model_validator(mode="after")
    def validate_recording_state(self) -> CallRecord:
        """Keep lifecycle state aligned with persisted recording evidence."""
        if (
            self.recording is not None
            and self.recording_state is not RecordingState.AVAILABLE
        ):
            raise ValueError(
                "recording_state must be 'available' when recording evidence is present"
            )
        if self.recording_state is RecordingState.AVAILABLE and self.recording is None:
            raise ValueError(
                "recording evidence is required when recording_state is 'available'"
            )
        if (
            self.recording_state is RecordingState.FAILED
            and not self.recording_error_code
        ):
            raise ValueError(
                "recording_error_code is required when recording_state is 'failed'"
            )
        if (
            self.recording_state is not RecordingState.FAILED
            and self.recording_error_code is not None
        ):
            raise ValueError(
                "recording_error_code is allowed only when recording_state is 'failed'"
            )
        return self
