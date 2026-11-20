"""UCVE Voice Activity Detection (VAD) Provider Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.types.audio import AudioFrame


@dataclass
class VADConfig:
    """Configuration contract for VAD providers.

    ``min_speech_frames`` / ``min_silence_frames`` drive dual-counter
    hysteresis (32 ms canonical frames). Defaults preserve legacy behaviour
    (onset on the first speech frame, endpoint after ~96 ms of silence); the
    orchestrator raises these under the ``vad_timing`` feature flag.
    """

    sample_rate: int = 16000
    window_samples: int = 512
    threshold: float = 0.5
    min_speech_frames: int = 5
    min_silence_frames: int = 30


@dataclass(frozen=True)
class VADEvent:
    """Voice Activity Detection inference output event."""

    speech_start: bool
    speech_end: bool
    probability: float


class BaseVADProvider(ABC):
    """Abstract Base Class for VAD providers."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if provider is healthy and ready."""

    @abstractmethod
    def process_frame(self, frame: AudioFrame) -> VADEvent:
        """Process a single audio frame and return VAD event."""

    @abstractmethod
    def reset(self) -> None:
        """Reset VAD internal state."""
