"""Deterministic, explicitly test-only streaming provider implementations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig
from core.types.audio import AudioFrame


async def _delay(milliseconds: float) -> None:
    if milliseconds > 0:
        await asyncio.sleep(milliseconds / 1000.0)


class ScriptedSTT(BaseSTTProvider):
    provider_id = "test-stt"
    provider_mode = "test"

    def __init__(self, *, final_text: str, first_chunk_delay_ms: float = 0.0) -> None:
        self.final_text = final_text
        self.first_chunk_delay_ms = first_chunk_delay_ms
        self.cancellation_observed = False

    def health_check(self) -> bool:
        return True

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        config: STTConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[Transcript]:
        async for _ in audio_stream:
            if cancellation_token and cancellation_token.is_cancelled:
                self.cancellation_observed = True
                return
        await _delay(self.first_chunk_delay_ms)
        if cancellation_token and cancellation_token.is_cancelled:
            self.cancellation_observed = True
            return
        yield Transcript(
            text=self.final_text,
            is_final=True,
            confidence=1.0,
            language=config.language,
        )


class ScriptedLLM(BaseLLMProvider):
    provider_id = "test-llm"
    provider_mode = "test"

    def __init__(
        self,
        *,
        chunks: tuple[str, ...],
        first_chunk_delay_ms: float = 0.0,
        inter_chunk_delay_ms: float = 0.0,
    ) -> None:
        self.chunks = chunks
        self.first_chunk_delay_ms = first_chunk_delay_ms
        self.inter_chunk_delay_ms = inter_chunk_delay_ms
        self.cancellation_observed = False

    def health_check(self) -> bool:
        return True

    async def generate_stream(
        self,
        messages: list[dict[str, object]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        for index, text in enumerate(self.chunks):
            await _delay(
                self.first_chunk_delay_ms if index == 0 else self.inter_chunk_delay_ms
            )
            if cancellation_token and cancellation_token.is_cancelled:
                self.cancellation_observed = True
                return
            yield LLMStreamChunk(
                text=text,
                is_first_token=index == 0,
                finish_reason="stop" if index == len(self.chunks) - 1 else None,
            )


class ScriptedTTS(BaseTTSProvider):
    provider_id = "test-tts"
    provider_mode = "test"

    def __init__(
        self,
        *,
        chunks: tuple[bytes, ...],
        first_chunk_delay_ms: float = 0.0,
        inter_chunk_delay_ms: float = 0.0,
    ) -> None:
        self.chunks = chunks
        self.first_chunk_delay_ms = first_chunk_delay_ms
        self.inter_chunk_delay_ms = inter_chunk_delay_ms
        self.cancellation_observed = False

    def health_check(self) -> bool:
        return True

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        for index, pcm_data in enumerate(self.chunks):
            await _delay(
                self.first_chunk_delay_ms if index == 0 else self.inter_chunk_delay_ms
            )
            if cancellation_token and cancellation_token.is_cancelled:
                self.cancellation_observed = True
                return
            yield TTSChunk(
                pcm_data=pcm_data,
                native_sample_rate=config.sample_rate,
                is_final=index == len(self.chunks) - 1,
            )
