"""UCVE Listening / Speaking pipeline configuration (feature-flagged).

The master switch is the ``UCVE_PIPELINE_V2`` environment variable — a comma
separated list of enabled phase names. When empty (default) the orchestrator
retains legacy demo behaviour. The pseudo-phase ``production`` enables every
phase at once.

All tuning knobs read from the environment contract documented in
``docs/developer/PRODUCTION_VOICE_PIPELINE_UPGRADE_PLAN.md`` §8.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# Canonical frame: 512 samples @ 16 kHz mono PCM16 = 1024 bytes = 32 ms.
FRAME_MS: float = 32.0

# All recognised phase tokens for ``UCVE_PIPELINE_V2``.
ALL_PHASES: frozenset[str] = frozenset(
    {
        "quick_wins",
        "frame_slicing",
        "vad_timing",
        "noise_gate",
        "pre_roll",
        "barge_verify",
        "streaming_stt",
        "speaking_hardening",
        "tool_loop",
        "rag_speculative",
        "vad_worker",
        "production",
    }
)


def ms_to_frames(ms: float, frame_ms: float = FRAME_MS) -> int:
    """Convert a millisecond duration to a count of 32 ms canonical frames."""
    return max(1, round(ms / frame_ms))


def _parse_phases(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip())


def _env_str(name: str, default: str) -> str:
    val = os.environ.get(name)
    return val if val is not None else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(float(raw.strip()))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class ListeningPipelineConfig:
    """Feature-flagged configuration for the ingress / listening path."""

    enabled_phases: frozenset[str] = field(default_factory=frozenset)

    # VAD timing (§8.2)
    vad_threshold: float = 0.5
    vad_min_speech_ms: int = 160
    vad_min_silence_ms: int = 960
    vad_pre_speech_ms: int = 200

    # Adaptive noise gate (§8.2)
    noise_gate_k: float = 3.0
    noise_gate_window: int = 50
    noise_gate_default_floor: float = 0.015

    # Barge-in verification (§8.3)
    barge_verify_window_ms: int = 700
    barge_min_sustained_speech_ms: int = 300
    barge_text_backup_words: int = 3

    # STT (§8.4)
    gladia_endpointing: float = 0.2
    gladia_receive_partials: bool = True
    stt_mock_text: str = ""
    stt_connect_timeout_ms: int = 3000
    stt_reconnect_max_attempts: int = 3
    ingress_backpressure_warn_ms: int = 100

    # Observability (§8.7)
    debug_listening: bool = False

    # --- phase predicates -------------------------------------------------
    def has_phase(self, phase: str) -> bool:
        return "production" in self.enabled_phases or phase in self.enabled_phases

    @property
    def enable_quick_wins(self) -> bool:
        # Any V2 phase implies the Phase-0 quick wins are safe to apply.
        return bool(self.enabled_phases)

    @property
    def enable_frame_slicing(self) -> bool:
        return self.has_phase("frame_slicing")

    @property
    def enable_vad_timing(self) -> bool:
        return self.has_phase("vad_timing")

    @property
    def enable_noise_gate(self) -> bool:
        return self.has_phase("noise_gate")

    @property
    def enable_pre_roll(self) -> bool:
        return self.has_phase("pre_roll")

    @property
    def enable_barge_verify(self) -> bool:
        return self.has_phase("barge_verify")

    @property
    def enable_streaming_stt(self) -> bool:
        return self.has_phase("streaming_stt")

    @property
    def enable_rag_speculative(self) -> bool:
        return self.has_phase("rag_speculative")

    @property
    def enable_vad_worker(self) -> bool:
        return self.has_phase("vad_worker")

    @property
    def use_speech_capture(self) -> bool:
        """True when any listening component beyond raw VAD is enabled."""
        return (
            self.enable_frame_slicing
            or self.enable_vad_timing
            or self.enable_noise_gate
            or self.enable_pre_roll
        )

    # --- derived timings --------------------------------------------------
    @property
    def vad_min_speech_frames(self) -> int:
        return ms_to_frames(self.vad_min_speech_ms)

    @property
    def vad_min_silence_frames(self) -> int:
        return ms_to_frames(self.vad_min_silence_ms)

    @property
    def pre_speech_bytes(self) -> int:
        # ms * 16 samples/ms * 2 bytes/sample
        return int(self.vad_pre_speech_ms * 16 * 2)

    @classmethod
    def from_env(cls) -> ListeningPipelineConfig:
        return cls(
            enabled_phases=_parse_phases(os.environ.get("UCVE_PIPELINE_V2")),
            vad_threshold=_env_float("UCVE_VAD_THRESHOLD", 0.5),
            vad_min_speech_ms=_env_int("UCVE_VAD_MIN_SPEECH_MS", 160),
            vad_min_silence_ms=_env_int("UCVE_VAD_MIN_SILENCE_MS", 960),
            vad_pre_speech_ms=_env_int("UCVE_VAD_PRE_SPEECH_MS", 200),
            noise_gate_k=_env_float("UCVE_NOISE_GATE_K", 3.0),
            noise_gate_window=_env_int("UCVE_NOISE_GATE_WINDOW", 50),
            noise_gate_default_floor=_env_float("UCVE_NOISE_GATE_DEFAULT_FLOOR", 0.015),
            barge_verify_window_ms=_env_int("UCVE_BARGE_VERIFY_WINDOW_MS", 700),
            barge_min_sustained_speech_ms=_env_int(
                "UCVE_BARGE_MIN_SUSTAINED_SPEECH_MS", 300
            ),
            barge_text_backup_words=_env_int("UCVE_BARGE_TEXT_BACKUP_WORDS", 3),
            gladia_endpointing=_env_float("UCVE_GLADIA_ENDPOINTING", 0.2),
            gladia_receive_partials=_env_bool("UCVE_GLADIA_RECEIVE_PARTIALS", True),
            stt_mock_text=_env_str("UCVE_STT_MOCK_TEXT", ""),
            stt_connect_timeout_ms=_env_int("UCVE_STT_CONNECT_TIMEOUT_MS", 3000),
            stt_reconnect_max_attempts=_env_int(
                "UCVE_STT_RECONNECT_MAX_ATTEMPTS", 3
            ),
            ingress_backpressure_warn_ms=_env_int(
                "UCVE_INGRESS_BACKPRESSURE_WARN_MS", 100
            ),
            debug_listening=_env_bool("UCVE_DEBUG_LISTENING", False),
        )


@dataclass(frozen=True)
class SpeakingPipelineConfig:
    """Feature-flagged configuration for the egress / speaking path."""

    enabled_phases: frozenset[str] = field(default_factory=frozenset)

    # TTS / egress (§8.5)
    tts_chunk_size_bytes: int = 8192
    egress_prebuffer_ms: int = 35
    tts_first_chunk_timeout_ms: int = 3000
    tts_inter_chunk_timeout_ms: int = 3000
    tts_overall_timeout_ms: int = 30000

    # LLM / chunking (§8.6)
    chunker_first_words: int = 2
    chunker_min_words: int = 3
    tool_filler_delay_ms: int = 400

    # Observability
    debug_latency: bool = False

    def has_phase(self, phase: str) -> bool:
        return "production" in self.enabled_phases or phase in self.enabled_phases

    @property
    def enable_speaking_hardening(self) -> bool:
        return self.has_phase("speaking_hardening")

    @property
    def enable_tool_loop(self) -> bool:
        return self.has_phase("tool_loop")

    @classmethod
    def from_env(cls) -> SpeakingPipelineConfig:
        return cls(
            enabled_phases=_parse_phases(os.environ.get("UCVE_PIPELINE_V2")),
            tts_chunk_size_bytes=_env_int("UCVE_TTS_CHUNK_SIZE_BYTES", 8192),
            egress_prebuffer_ms=_env_int("UCVE_EGRESS_PREBUFFER_MS", 35),
            tts_first_chunk_timeout_ms=_env_int(
                "UCVE_TTS_FIRST_CHUNK_TIMEOUT_MS", 3000
            ),
            tts_inter_chunk_timeout_ms=_env_int(
                "UCVE_TTS_INTER_CHUNK_TIMEOUT_MS", 3000
            ),
            tts_overall_timeout_ms=_env_int("UCVE_TTS_OVERALL_TIMEOUT_MS", 30000),
            chunker_first_words=_env_int("UCVE_CHUNKER_FIRST_WORDS", 2),
            chunker_min_words=_env_int("UCVE_CHUNKER_MIN_WORDS", 3),
            tool_filler_delay_ms=_env_int("UCVE_TOOL_FILLER_DELAY_MS", 400),
            debug_latency=_env_bool("UCVE_DEBUG_LATENCY", False),
        )
