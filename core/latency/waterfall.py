"""Per-turn latency timestamps with explicit clock and measurement quality."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class StageBudget(BaseModel):
    """Latency budget bounds for a single pipeline stage."""

    name: str
    budget_ms: float
    warn_ms: float


def _duration(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or end < start:
        return None
    return round(end - start, 3)


class LatencyWaterfall(BaseModel):
    """Truthful latency trace for one turn.

    Server timestamps use one monotonic clock. Client timestamps are retained in
    their own clock domain and are never subtracted from server timestamps.
    """

    schema_version: str = "1.0"
    session_id: UUID
    turn_id: UUID = Field(default_factory=uuid4)
    clock_domain: str = "server_monotonic_ms"

    acoustic_end_ms: float | None = None
    vad_end_of_speech_ms: float | None = None
    stt_final_ms: float | None = None
    rag_retrieve_ms: float | None = None
    llm_ttft_ms: float | None = None
    chunker_ms: float | None = None
    tts_ttfb_ms: float | None = None
    server_send_ms: float | None = None
    playback_ack_received_ms: float | None = None

    client_clock_domain: str = "client_performance_ms"
    client_scheduled_playback_ms: float | None = None
    client_playback_started_ms: float | None = None

    # Compatibility field for old same-clock callers. New runtime code does not
    # set this from server enqueue or client wall-clock timestamps.
    playback_start_ms: float | None = None
    total_e2e_ms: float = 0.0

    measurement_quality: str = "incomplete"
    excluded_reason: str | None = None
    playback_underrun: bool | None = None
    prebuffer_ms: float | None = None
    dropped_input_frames: int = 0
    dropped_output_chunks: int = 0
    queue_high_water: int = 0

    def user_perceived_latency_ms(self) -> float | None:
        """Return the server-clock acoustic-end to playback-ack upper bound."""
        if self.excluded_reason:
            return None
        return _duration(self.acoustic_end_ms, self.playback_ack_received_ms)

    def compute_e2e_latency(self) -> float:
        """Compute a compatible numeric value without fabricating missing data."""
        measured = self.user_perceived_latency_ms()
        if measured is None:
            measured = _duration(self.vad_end_of_speech_ms, self.playback_start_ms)
        self.total_e2e_ms = measured if measured is not None else 0.0
        return self.total_e2e_ms

    def missing_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self.acoustic_end_ms is None:
            reasons.append("acoustic_end_missing")
        if self.vad_end_of_speech_ms is None:
            reasons.append("vad_end_missing")
        if self.stt_final_ms is None:
            reasons.append("stt_final_missing")
        if self.server_send_ms is None:
            reasons.append("server_send_missing")
        if self.playback_ack_received_ms is None:
            reasons.append("playback_ack_missing")
        if self.excluded_reason:
            reasons.append(f"excluded:{self.excluded_reason}")
        return reasons

    def stage_durations_ms(self) -> dict[str, float | None]:
        """Return stage durations only when both same-clock anchors exist."""
        llm_start = self.rag_retrieve_ms or self.stt_final_ms
        tts_start = self.chunker_ms or self.llm_ttft_ms
        return {
            "vad_tail": _duration(self.acoustic_end_ms, self.vad_end_of_speech_ms),
            "stt_after_acoustic_end": _duration(
                self.acoustic_end_ms, self.stt_final_ms
            ),
            "stt_after_vad": _duration(self.vad_end_of_speech_ms, self.stt_final_ms),
            "rag": _duration(self.stt_final_ms, self.rag_retrieve_ms),
            "llm_ttft": _duration(llm_start, self.llm_ttft_ms),
            "tts_ttfb": _duration(tts_start, self.tts_ttfb_ms),
            "server_send": _duration(self.tts_ttfb_ms, self.server_send_ms),
            "user_perceived_e2e": self.user_perceived_latency_ms(),
        }

    def to_metric_payload(self) -> dict[str, Any]:
        """Serialize the canonical versioned ``metric.latency`` payload."""
        e2e = self.user_perceived_latency_ms()
        quality = self.measurement_quality
        if e2e is not None and quality == "incomplete":
            quality = "server_ack_upper_bound"
        return {
            "kind": "latency",
            "schema_version": self.schema_version,
            "session_id": str(self.session_id),
            "turn_id": str(self.turn_id),
            "clock_domain": self.clock_domain,
            "client_clock_domain": self.client_clock_domain,
            "measurement_quality": quality,
            "timestamps_ms": {
                "acoustic_end": self.acoustic_end_ms,
                "vad_end": self.vad_end_of_speech_ms,
                "stt_final": self.stt_final_ms,
                "rag_end": self.rag_retrieve_ms,
                "llm_first_token": self.llm_ttft_ms,
                "first_speakable_text": self.chunker_ms,
                "tts_first_byte": self.tts_ttfb_ms,
                "server_send": self.server_send_ms,
                "playback_ack_received": self.playback_ack_received_ms,
                "client_scheduled_playback": self.client_scheduled_playback_ms,
                "client_playback_started": self.client_playback_started_ms,
            },
            "durations_ms": self.stage_durations_ms(),
            "queue": {
                "high_water": self.queue_high_water,
                "dropped_input_frames": self.dropped_input_frames,
                "dropped_output_chunks": self.dropped_output_chunks,
                "prebuffer_ms": self.prebuffer_ms,
                "underrun": self.playback_underrun,
            },
            "missing_reasons": self.missing_reasons(),
            "excluded_reason": self.excluded_reason,
            "slo": {"status": "provisional", "breached": None},
        }
