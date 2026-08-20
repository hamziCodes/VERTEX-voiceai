"""UCVE Null VAD Test Adapter."""

from __future__ import annotations

from core.providers.interfaces.vad import BaseVADProvider, VADEvent
from core.types.audio import AudioFrame


class NullVADProvider(BaseVADProvider):
    """No-op VAD provider implementation for testing."""

    def health_check(self) -> bool:
        return True

    def process_frame(self, frame: AudioFrame) -> VADEvent:
        return VADEvent(speech_start=False, speech_end=False, probability=0.0)

    def reset(self) -> None:
        pass
