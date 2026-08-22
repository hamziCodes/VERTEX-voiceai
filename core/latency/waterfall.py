"""LatencyWaterfall & StageBudget Data Models — Cascaded per-turn latency tracing."""

from __future__ import annotations

from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class StageBudget(BaseModel):
    """Latency budget bounds for a single pipeline stage."""

    name: str
    budget_ms: float
    warn_ms: float


class LatencyWaterfall(BaseModel):
    """Cascaded per-turn latency waterfall trace model."""

    session_id: UUID
    turn_id: UUID = Field(default_factory=uuid4)
    vad_end_of_speech_ms: float = 0.0
    stt_final_ms: float = 0.0
    rag_retrieve_ms: float = 0.0
    llm_ttft_ms: float = 0.0
    chunker_ms: float = 0.0
    tts_ttfb_ms: float = 0.0
    playback_start_ms: float = 0.0
    total_e2e_ms: float = 0.0

    def compute_e2e_latency(self) -> float:
        """Compute end-to-end latency from VAD speech-end to client playback start."""
        if self.playback_start_ms > 0 and self.vad_end_of_speech_ms > 0:
            self.total_e2e_ms = max(0.0, self.playback_start_ms - self.vad_end_of_speech_ms)
        elif self.tts_ttfb_ms > 0 and self.vad_end_of_speech_ms > 0:
            self.total_e2e_ms = max(0.0, self.tts_ttfb_ms - self.vad_end_of_speech_ms)
        return self.total_e2e_ms
