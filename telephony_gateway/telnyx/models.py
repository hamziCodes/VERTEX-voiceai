"""Strict Telnyx Voice API webhook envelope models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class TelnyxEventType(StrEnum):
    CALL_INITIATED = "call.initiated"
    CALL_ANSWERED = "call.answered"
    CALL_HANGUP = "call.hangup"
    CALL_DTMF_RECEIVED = "call.dtmf.received"
    CALL_STREAMING_STARTED = "call.streaming.started"
    CALL_STREAMING_STOPPED = "call.streaming.stopped"
    CALL_STREAMING_FAILED = "call.streaming.failed"


class TelnyxCallPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    call_control_id: str = Field(min_length=1, max_length=512)
    call_leg_id: str = Field(min_length=1, max_length=128)
    call_session_id: str = Field(min_length=1, max_length=128)
    connection_id: str = Field(min_length=1, max_length=128)
    from_number: str = Field(alias="from", pattern=r"^\+[1-9]\d{7,14}$")
    to: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    direction: Literal["incoming", "outgoing"] | None = None


class TelnyxEventData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    event_type: TelnyxEventType
    occurred_at: AwareDatetime
    record_type: Literal["event"]
    payload: TelnyxCallPayload

    @field_validator("occurred_at")
    @classmethod
    def finite_datetime(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class TelnyxWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TelnyxEventData
    meta: dict[str, Any] | None = None


class TelnyxAcceptedEvent(BaseModel):
    event_id: UUID
    event_type: TelnyxEventType
    duplicate: bool = False
