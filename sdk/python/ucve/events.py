"""Typed realtime telemetry payloads shared with the wire schema."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AudioStartPayload(TypedDict):
    turn_id: str
    server_send_ms: float
    clock_domain: Literal["server_monotonic_ms"]


class PlaybackStartedPayload(TypedDict):
    kind: Literal["playback_started"]
    turn_id: str
    client_clock_domain: Literal["client_performance_ms"]
    client_playback_started_ms: float
    client_scheduled_playback_ms: float | None
    audio_context_time_sec: float | None
    prebuffer_ms: float | None
    underrun: bool | None


class LatencyMetricPayload(TypedDict):
    kind: Literal["latency"]
    schema_version: Literal["1.0"]
    session_id: str
    turn_id: str
    clock_domain: Literal["server_monotonic_ms"]
    client_clock_domain: Literal["client_performance_ms"]
    measurement_quality: Literal[
        "incomplete", "playback_ack_only", "server_ack_upper_bound", "excluded"
    ]
    timestamps_ms: dict[str, float | None]
    durations_ms: dict[str, float | None]
    queue: dict[str, Any]
    missing_reasons: list[str]


class ClearAudioPayload(TypedDict):
    turn_id: str | None
    sequence: int
    reason: str


class PlaybackDrainedPayload(TypedDict):
    turn_id: str
    played_audio_ms: float


class PlayedTextCommitPayload(TypedDict):
    turn_id: str
    text: str
    played_audio_ms: float
    complete: bool
