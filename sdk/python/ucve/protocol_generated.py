"""Generated from sdk/shared/event_schema.json. Do not edit."""

from __future__ import annotations

from typing import Any, Final, Literal, TypedDict

PROTOCOL_VERSION: Final = "1.0.0"
SUPPORTED_PROTOCOL_RANGE: Final = ">=1.0.0 <2.0.0"

RealtimeEventType = Literal[
    "protocol.hello",
    "session.ready",
    "control.ping",
    "control.pong",
    "text.turn",
    "transcript.partial",
    "transcript.final",
    "transcript",
    "audio.start",
    "audio.end",
    "control.playback_started",
    "control.barge_in",
    "control.clear_audio",
    "control.clear_audio_ack",
    "control.playback_drained",
    "assistant.played_text_commit",
    "metric.latency",
    "session.token_expiring",
    "session.close",
    "error",
    "degraded",
]


class RealtimeEvent(TypedDict):
    protocol_version: str
    event_id: str
    sequence: int
    event_type: RealtimeEventType
    timestamp_ms: float
    payload: dict[str, Any]
