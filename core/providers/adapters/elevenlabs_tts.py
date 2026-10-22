"""UCVE ElevenLabs TTS adapter (PCM stream; mock when key unset)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.exceptions import (
    ProviderInvocationError,
    classify_http_failure,
    provider_invocation_error,
)
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig
from core.providers.mode import should_use_mock_provider

logger = get_logger("ucve.providers.elevenlabs")

_DEFAULT_VOICE = "hpp4J3VqNfWAUOO0d1Us"
_API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


def _tone_pcm(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    import math
    import struct

    n = int(sample_rate * duration_ms / 1000)
    out = bytearray()
    for i in range(n):
        sample = int(5000 * math.sin(2 * math.pi * 523.25 * i / sample_rate))
        out.extend(struct.pack("<h", sample))
    return bytes(out)


class ElevenLabsTTSProvider(BaseTTSProvider):
    """ElevenLabs streaming TTS → raw PCM (English-friendly)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
        chunk_size_bytes: int = 3200,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.chunk_size_bytes = max(320, int(chunk_size_bytes))
        self._model = (
            model
            or os.environ.get("ELEVENLABS_MODEL_ID")
            or "eleven_multilingual_v2"
        ).strip()
        # Default pcm_16000 matches WS egress — avoids per-chunk 22.05→16k resample artifacts.
        self._output_format = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "pcm_16000")
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def health_check(self) -> bool:
        return True

    def _resolve_voice(self, config: TTSConfig) -> str:
        voice = (config.voice_id or "").strip()
        if voice and voice != "default":
            return voice
        return (
            os.environ.get("ELEVENLABS_VOICE_ID")
            or os.environ.get("PLATFORM_ELEVENLABS_VOICE_ID")
            or _DEFAULT_VOICE
        )

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        use_mock = should_use_mock_provider(
            provider_id="elevenlabs", api_key=self.api_key
        )
        if use_mock:
            pcm = _tone_pcm(duration_ms=max(100, min(2000, len(text) * 40)))
            for i in range(0, len(pcm), self.chunk_size_bytes):
                if cancellation_token and cancellation_token.is_cancelled:
                    return
                part = pcm[i : i + self.chunk_size_bytes]
                yield TTSChunk(
                    pcm_data=part,
                    native_sample_rate=16000,
                    is_final=(i + self.chunk_size_bytes >= len(pcm)),
                )
            return

        voice = self._resolve_voice(config)
        url = _API.format(voice_id=voice)
        # Query output_format for stream endpoint (ElevenLabs v1).
        params = {"output_format": self._output_format}
        payload = {
            "text": text,
            "model_id": self._model,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        logger.info(
            "Initiating ElevenLabs TTS synthesis request",
            text_len=len(text),
            voice_id=voice,
            output_format=self._output_format,
        )
        client = self._get_client()
        try:
            async with client.stream(
                "POST",
                url,
                params=params,
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/octet-stream",
                },
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    logger.error(
                        "ElevenLabs TTS API call failed",
                        status_code=resp.status_code,
                    )
                    raise ProviderInvocationError(
                        classify_http_failure("elevenlabs", resp.status_code)
                    )

                native_rate = 16000
                if "24000" in self._output_format:
                    native_rate = 24000
                elif "22050" in self._output_format:
                    native_rate = 22050
                elif "44100" in self._output_format:
                    native_rate = 44100
                buf = bytearray()
                emitted_first_audio = False
                async for raw in resp.aiter_bytes():
                    if cancellation_token and cancellation_token.is_cancelled:
                        return
                    if not raw:
                        continue
                    buf.extend(raw)
                    if not emitted_first_audio and len(buf) >= 2:
                        take = len(buf) - (len(buf) % 2)
                        part = bytes(buf[:take])
                        del buf[:take]
                        emitted_first_audio = True
                        yield TTSChunk(
                            pcm_data=part,
                            native_sample_rate=native_rate,
                            is_final=False,
                        )
                    while len(buf) >= self.chunk_size_bytes:
                        # Keep even byte alignment for int16 PCM.
                        take = self.chunk_size_bytes - (self.chunk_size_bytes % 2)
                        part = bytes(buf[:take])
                        del buf[:take]
                        yield TTSChunk(
                            pcm_data=part,
                            native_sample_rate=native_rate,
                            is_final=False,
                        )
                if buf:
                    if len(buf) % 2 == 1:
                        buf = buf[:-1]
                    if buf:
                        yield TTSChunk(
                            pcm_data=bytes(buf),
                            native_sample_rate=native_rate,
                            is_final=True,
                        )
                else:
                    yield TTSChunk(
                        pcm_data=b"",
                        native_sample_rate=native_rate,
                        is_final=True,
                    )
        except ProviderInvocationError:
            await self.aclose()
            raise
        except Exception as exc:
            logger.error("ElevenLabs TTS exception", error_type=type(exc).__name__)
            await self.aclose()
            raise provider_invocation_error("elevenlabs", exc) from exc
