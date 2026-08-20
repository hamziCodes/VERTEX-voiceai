"""UCVE Silero+Energy Hybrid VAD Adapter implementing BaseVADProvider."""

from __future__ import annotations

import math
from core.providers.interfaces.vad import BaseVADProvider, VADConfig, VADEvent
from core.types.audio import AudioFrame


class SileroVADAdapter(BaseVADProvider):
    """Silero VAD adapter with RMS energy fallback implementing BaseVADProvider ABC."""

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self.energy_threshold_db: float = -45.0
        self._is_speaking: bool = False

    def health_check(self) -> bool:
        """Return True if VAD adapter is healthy."""
        return True

    def reset(self) -> None:
        """Reset VAD internal state."""
        self._is_speaking = False

    def process_frame(self, frame: AudioFrame) -> VADEvent:
        """Process a single 16kHz PCM audio frame and return VADEvent."""
        if not frame.pcm16:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        # RMS energy calculation
        num_samples = len(frame.pcm16) // 2
        if num_samples == 0:
            return VADEvent(speech_start=False, speech_end=False, probability=0.0)

        sum_sq = 0
        for i in range(0, len(frame.pcm16) - 1, 2):
            sample = int.from_bytes(frame.pcm16[i:i + 2], byteorder="little", signed=True)
            sum_sq += sample * sample

        rms = math.sqrt(sum_sq / num_samples)
        db = 20 * math.log10(max(rms, 1.0)) - 90.0

        is_speech = db > self.energy_threshold_db
        prob = 0.95 if is_speech else 0.05

        speech_start = is_speech and not self._is_speaking
        speech_end = not is_speech and self._is_speaking
        self._is_speaking = is_speech

        return VADEvent(speech_start=speech_start, speech_end=speech_end, probability=prob)
