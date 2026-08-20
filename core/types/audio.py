"""UCVE Canonical Audio Types & Frame Contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.types.constants import CANONICAL_CHANNELS, CANONICAL_SAMPLE_RATE
from core.types.resampler import Resampler, SUPPORTED_RATES

__all__ = [
    "AudioEncoding",
    "AudioFrame",
    "Resampler",
    "SUPPORTED_RATES",
]


class AudioEncoding(str, Enum):
    """Wire & transport audio encodings."""

    PCM16 = "pcm16"
    MULAW = "mulaw"
    OPUS = "opus"


@dataclass(frozen=True)
class AudioFrame:
    """Immutable, transport-agnostic canonical audio frame object."""

    pcm16: bytes
    sample_rate: int = CANONICAL_SAMPLE_RATE
    timestamp_ms: float = 0.0
    sequence: int = 0
    channel_count: int = CANONICAL_CHANNELS
    contains_speech: bool | None = None

    def __post_init__(self) -> None:
        if len(self.pcm16) % 2 != 0:
            raise ValueError(
                f"PCM16 data length must be even (2 bytes per sample). Got {len(self.pcm16)} bytes."
            )
        if self.sample_rate <= 0:
            raise ValueError(f"Sample rate must be positive. Got {self.sample_rate}.")
        if self.channel_count <= 0:
            raise ValueError(f"Channel count must be positive. Got {self.channel_count}.")

    @property
    def sample_count(self) -> int:
        """Total audio samples in frame."""
        return len(self.pcm16) // (2 * self.channel_count)

    @property
    def duration_ms(self) -> float:
        """Duration of audio frame in milliseconds."""
        return (self.sample_count / self.sample_rate) * 1000.0
