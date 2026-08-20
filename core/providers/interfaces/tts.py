"""UCVE Text-to-Speech (TTS) Provider Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.buffers.cancellation import CancellationToken


@dataclass
class TTSConfig:
    """Configuration contract for TTS providers."""

    voice_id: str
    sample_rate: int = 22050
    speed: float = 1.0
    encoding: str = "pcm16"


@dataclass(frozen=True)
class TTSChunk:
    """TTS audio synthesis output chunk with provider-native sample rate metadata."""

    pcm_data: bytes
    native_sample_rate: int = 22050
    is_final: bool = False
    timestamp_ms: float = 0.0


class BaseTTSProvider(ABC):
    """Abstract Base Class for TTS providers."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if provider is healthy and ready."""

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        """Stream synthesized PCM audio chunks from text input."""
