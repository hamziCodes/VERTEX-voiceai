"""UCVE Null STT Test Adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.types.audio import AudioFrame


class NullSTTProvider(BaseSTTProvider):
    """No-op STT provider implementation for testing."""

    def health_check(self) -> bool:
        return True

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        config: STTConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[Transcript]:
        async for _frame in audio_stream:
            if cancellation_token and cancellation_token.is_cancelled:
                break
            yield Transcript(text="", is_final=False, confidence=1.0, language=config.language)
