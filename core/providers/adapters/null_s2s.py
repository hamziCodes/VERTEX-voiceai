"""UCVE Null Speech-to-Speech (S2S) Test Adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.s2s import BaseSpeechToSpeechProvider, S2SConfig, S2SEvent
from core.types.audio import AudioFrame


class NullS2SProvider(BaseSpeechToSpeechProvider):
    """No-op Speech-to-Speech provider implementation for testing."""

    def health_check(self) -> bool:
        return True

    async def session_stream(
        self,
        input_stream: AsyncIterator[AudioFrame],
        config: S2SConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[S2SEvent]:
        async for _frame in input_stream:
            if cancellation_token and cancellation_token.is_cancelled:
                break
            yield S2SEvent(audio_data=b"", text="", event_type="audio")
