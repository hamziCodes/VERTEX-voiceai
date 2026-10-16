"""Shared lifecycle contract for provider streaming-STT sessions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from core.providers.interfaces.stt import Transcript


class BaseLiveSTTSession(ABC):
    """One warm streaming-STT connection owned by a voice session."""

    @property
    @abstractmethod
    def is_live(self) -> bool:
        """Whether audio can currently be accepted by the provider."""

    @abstractmethod
    async def start(self) -> bool:
        """Open the provider connection and return whether it became live."""

    @abstractmethod
    async def send_audio(self, pcm16: bytes) -> None:
        """Apply bounded backpressure while sending canonical PCM16 audio."""

    @abstractmethod
    def transcripts(self) -> AsyncIterator[Transcript]:
        """Yield ordered partial and final transcripts."""

    @abstractmethod
    async def close(self) -> None:
        """Close all provider resources and background tasks."""
