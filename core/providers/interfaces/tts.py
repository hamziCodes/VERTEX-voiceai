"""UCVE Text-to-Speech (TTS) Provider Interface."""

from __future__ import annotations

import asyncio
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


@dataclass(frozen=True)
class TTSStreamTimeouts:
    """Independent deadlines for starting, advancing, and completing TTS."""

    first_chunk_seconds: float = 3.0
    idle_seconds: float = 3.0
    overall_seconds: float = 30.0


class TTSStreamTimeoutError(TimeoutError):
    """A TTS stream missed a named deadline."""

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"TTS stream timeout: {stage}")


async def iterate_tts_stream(
    stream: AsyncIterator[TTSChunk],
    deadlines: TTSStreamTimeouts,
) -> AsyncIterator[TTSChunk]:
    """Yield a TTS stream while enforcing distinct first, idle, and total deadlines."""

    iterator = stream.__aiter__()
    first = True
    try:
        async with asyncio.timeout(deadlines.overall_seconds):
            while True:
                timeout = (
                    deadlines.first_chunk_seconds if first else deadlines.idle_seconds
                )
                try:
                    item = await asyncio.wait_for(anext(iterator), timeout=timeout)
                except StopAsyncIteration:
                    return
                except TimeoutError as exc:
                    stage = "first_chunk" if first else "inter_chunk_idle"
                    raise TTSStreamTimeoutError(stage) from exc
                first = False
                yield item
    except TimeoutError as exc:
        if isinstance(exc, TTSStreamTimeoutError):
            raise
        raise TTSStreamTimeoutError("overall") from exc


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
