"""UCVE Speech Capture Engine — gate + VAD + pre-roll orchestration.

Combines the adaptive noise gate (Phase 2), Silero/energy VAD hysteresis
(Phase 1) and the pre-speech ring buffer (Phase 3) into a single per-frame
``observe()`` call that returns a :class:`VADEvent` and manages the speech
capture buffer (with lookback) used for STT dispatch.

Legacy behaviour is unaffected unless the owning orchestrator opts in via
``ListeningPipelineConfig.use_speech_capture``.
"""

from __future__ import annotations

from core.listening.config import ListeningPipelineConfig
from core.listening.noise_gate import AdaptiveNoiseGate
from core.listening.pre_speech_buffer import PreSpeechRingBuffer
from core.providers.interfaces.vad import BaseVADProvider, VADEvent
from core.types.audio import AudioFrame

_MAX_CAPTURE_BYTES = 512 * 1024


class SpeechCaptureEngine:
    """Per-frame listening orchestrator producing VAD events + capture buffer."""

    def __init__(
        self,
        vad: BaseVADProvider,
        config: ListeningPipelineConfig,
    ) -> None:
        self._vad = vad
        self._config = config
        self._gate: AdaptiveNoiseGate | None = (
            AdaptiveNoiseGate(
                k=config.noise_gate_k,
                window=config.noise_gate_window,
                default_floor=config.noise_gate_default_floor,
            )
            if config.enable_noise_gate
            else None
        )
        self._preroll: PreSpeechRingBuffer | None = (
            PreSpeechRingBuffer(config.pre_speech_bytes)
            if config.enable_pre_roll
            else None
        )
        self._capture = bytearray()
        self._capturing = False
        self._last_rms = 0.0
        self._last_gated = False

    # --- state ------------------------------------------------------------
    @property
    def capturing(self) -> bool:
        return self._capturing

    @property
    def has_utterance(self) -> bool:
        return len(self._capture) > 0

    @property
    def last_rms(self) -> float:
        return self._last_rms

    @property
    def last_gated(self) -> bool:
        """True when the most recent frame was blocked by the noise gate."""
        return self._last_gated

    # --- capture control --------------------------------------------------
    def begin_capture(self, current_pcm: bytes = b"") -> None:
        """Start capturing, seeding with pre-roll lookback (or the current frame)."""
        self._capturing = True
        if self._preroll is not None:
            self._capture = bytearray(self._preroll.drain())
        else:
            self._capture = bytearray(current_pcm)

    def end_capture(self) -> None:
        self._capturing = False

    def take_utterance(self) -> bytes:
        """Return captured PCM (incl. pre-roll) and clear the capture buffer."""
        data = bytes(self._capture)
        self._capture = bytearray()
        return data

    def _append(self, pcm16: bytes) -> None:
        if len(self._capture) + len(pcm16) <= _MAX_CAPTURE_BYTES:
            self._capture.extend(pcm16)

    # --- per-frame processing --------------------------------------------
    def observe(self, frame: AudioFrame, agent_speaking: bool = False) -> VADEvent:
        """Process one canonical frame; returns the VAD event for this frame."""
        pcm = frame.pcm16 or b""

        if self._preroll is not None:
            self._preroll.push(pcm)

        effective = frame
        self._last_gated = False
        if self._gate is not None and pcm:
            self._last_rms = self._gate.compute_rms(pcm)
            passed = self._gate.is_speech(
                pcm,
                agent_speaking=agent_speaking,
                user_speaking=self._capturing,
            )
            if not passed:
                # Ambient noise: feed the VAD a silent frame so onset counters
                # never accumulate on room hum while keeping endpoint bookkeeping.
                self._last_gated = True
                effective = AudioFrame(
                    pcm16=b"\x00\x00" * (len(pcm) // 2),
                    sample_rate=frame.sample_rate,
                    channel_count=frame.channel_count,
                )

        evt = self._vad.process_frame(effective)

        started_now = False
        if evt.speech_start and not agent_speaking and not self._capturing:
            self.begin_capture(pcm)
            started_now = True

        if self._capturing and pcm and not started_now:
            self._append(pcm)

        if evt.speech_end and self._capturing:
            self.end_capture()

        return evt

    def reset(self) -> None:
        self._capture = bytearray()
        self._capturing = False
        self._last_rms = 0.0
        self._last_gated = False
        if self._gate is not None:
            self._gate.reset()
        if self._preroll is not None:
            self._preroll.reset()
        self._vad.reset()
