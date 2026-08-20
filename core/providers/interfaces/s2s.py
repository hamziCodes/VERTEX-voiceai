"""UCVE Speech-to-Speech (S2S) Provider Interface (Stub Contract)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from core.buffers.cancellation import CancellationToken
from core.types.audio import AudioFrame


@dataclass
class S2SConfig:
    """Configuration contract for Speech-to-Speech providers."""

    voice_id: str = "default"
    model: str = "s2s-v1"
    language: str = "en"


@dataclass(frozen=True)
class S2SEvent:
    """Speech-to-Speech streaming response event."""

    audio_data: bytes = b""
    text: str = ""
    event_type: str = "audio"
    native_sample_rate: int = 24000


class BaseSpeechToSpeechProvider(ABC):
    """Abstract Base Class for Speech-to-Speech (S2S) providers."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if provider is healthy and ready."""

    @abstractmethod
    def session_stream(
        self,
        input_stream: AsyncIterator[AudioFrame],
        config: S2SConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[S2SEvent]:
        """Stream bi-directional S2S events from incoming audio frames."""
