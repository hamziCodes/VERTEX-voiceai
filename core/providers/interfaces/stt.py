"""UCVE Speech-to-Text (STT) Provider Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.buffers.cancellation import CancellationToken
from core.types.audio import AudioFrame


@dataclass
class STTConfig:
    """Configuration contract for STT providers."""

    language: str = "en"
    code_switching: bool = False
    endpointing_seconds: float = 0.2
    sample_rate: int = 16000

    def __post_init__(self) -> None:
        if not self.language:
            raise ValueError("STTConfig language must not be empty.")


@dataclass(frozen=True)
class Transcript:
    """STT transcript hypothesis."""

    text: str
    is_final: bool = False
    confidence: float | None = None
    language: str | None = None
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0


class BaseSTTProvider(ABC):
    """Abstract Base Class for STT providers."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if provider is healthy and ready."""

    @abstractmethod
    def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        config: STTConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[Transcript]:
        """Stream transcription chunks from incoming audio frames."""
