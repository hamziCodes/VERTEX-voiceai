"""UCVE Null TTS Test Adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig


class NullTTSProvider(BaseTTSProvider):
    """No-op TTS provider implementation for testing."""

    def health_check(self) -> bool:
        return True

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        # Simple test mock output
        chunks = [
            TTSChunk(pcm_data=b"\x00\x00" * 160, native_sample_rate=config.sample_rate, is_final=True)
        ]
        for chunk in chunks:
            if cancellation_token and cancellation_token.is_cancelled:
                break
            yield chunk
