"""UCVE Uplift TTS adapter (mock PCM when key unset)."""

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

logger = get_logger("ucve.providers.uplift")


class _PCMResponseDecoder:
    """Incrementally remove a RIFF/WAVE container while passing raw PCM through."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._mode: str | None = None
        self._data_remaining: int | None = None
        self.sample_rate: int | None = None

    def feed(self, chunk: bytes) -> bytes:
        if not chunk:
            return b""
        if self._mode == "raw":
            return chunk
        self._buffer.extend(chunk)
        if self._mode is None:
            if len(self._buffer) < 4:
                return b""
            if self._buffer[:4] != b"RIFF":
                self._mode = "raw"
                output = bytes(self._buffer)
                self._buffer.clear()
                return output
            self._mode = "wave_header"
        if self._mode == "wave_header":
            return self._parse_wave_header()
        return self._take_wave_data()

    def _parse_wave_header(self) -> bytes:
        if len(self._buffer) > 65536:
            raise ValueError("RIFF/WAVE header exceeds 64 KiB.")
        if len(self._buffer) < 12:
            return b""
        if self._buffer[8:12] != b"WAVE":
            raise ValueError("Unsupported RIFF payload: expected WAVE container.")
        offset = 12
        while True:
            if len(self._buffer) < offset + 8:
                return b""
            chunk_id = bytes(self._buffer[offset : offset + 4])
            chunk_size = int.from_bytes(self._buffer[offset + 4 : offset + 8], "little")
            data_start = offset + 8
            if chunk_id == b"data":
                del self._buffer[:data_start]
                self._data_remaining = chunk_size
                self._mode = "wave_data"
                return self._take_wave_data()
            padded_size = chunk_size + (chunk_size % 2)
            if len(self._buffer) < data_start + padded_size:
                return b""
            if chunk_id == b"fmt " and chunk_size >= 16:
                self.sample_rate = int.from_bytes(
                    self._buffer[data_start + 4 : data_start + 8], "little"
                )
            offset = data_start + padded_size

    def _take_wave_data(self) -> bytes:
        if self._data_remaining is None or self._data_remaining <= 0:
            return b""
        take = min(len(self._buffer), self._data_remaining)
        output = bytes(self._buffer[:take])
        del self._buffer[:take]
        self._data_remaining -= take
        return output


def _tone_pcm(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    """Generate a short audible tone for mock TTS egress."""
    import math
    import struct

    n = int(sample_rate * duration_ms / 1000)
    freq = 440.0
    out = bytearray()
    for i in range(n):
        sample = int(6000 * math.sin(2 * math.pi * freq * i / sample_rate))
        out.extend(struct.pack("<h", sample))
    return bytes(out)


class UpliftTTSProvider(BaseTTSProvider):
    """Uplift TTS REST adapter. Emits mock PCM when UPLIFT_API_KEY unset."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        chunk_size_bytes: int = 3200,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self._base = os.environ.get("UPLIFT_API_BASE", "https://api.upliftai.org")
        self._synth_path = os.environ.get(
            "UPLIFT_TTS_PATH", "/v1/synthesis/text-to-speech"
        )
        self._client: httpx.AsyncClient | None = None
        # Output batching: larger chunks smooth WS throughput (Phase 6).
        self.chunk_size_bytes = max(320, int(chunk_size_bytes))
        # Prefer 16 kHz PCM to match sovereign WS egress.
        # Override with UPLIFT_OUTPUT_FORMAT when required.
        self._output_format = os.environ.get("UPLIFT_OUTPUT_FORMAT", "PCM_16000_16")

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

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        use_mock = should_use_mock_provider(provider_id="uplift", api_key=self.api_key)
        if use_mock:
            if not self.api_key:
                logger.info("Uplift TTS API key not set — using Mock TTS provider.")
            pcm = _tone_pcm(duration_ms=max(100, min(2000, len(text) * 40)))
            chunk_size = self.chunk_size_bytes
            for i in range(0, len(pcm), chunk_size):
                if cancellation_token and cancellation_token.is_cancelled:
                    return
                part = pcm[i : i + chunk_size]
                yield TTSChunk(
                    pcm_data=part,
                    native_sample_rate=16000,
                    is_final=(i + chunk_size >= len(pcm)),
                )
            return

        client = self._get_client()
        try:
            voice = config.voice_id
            if not voice or voice == "default":
                voice = (
                    os.environ.get("UPLIFT_VOICE_ID")
                    or os.environ.get("PLATFORM_UPLIFT_VOICE_ID")
                    or "v_meklc281"
                )
            logger.info(
                "Initiating Uplift TTS synthesis request",
                text_len=len(text),
                voice_id=voice,
                output_format=self._output_format,
            )
            fmt = self._output_format.upper()
            if "22050" in fmt:
                native_rate = 22050
            elif "24000" in fmt:
                native_rate = 24000
            elif "16000" in fmt:
                native_rate = 16000
            else:
                native_rate = config.sample_rate
            decoder = _PCMResponseDecoder()
            audio_buffer = bytearray()
            emitted_first_audio = False
            async with client.stream(
                "POST",
                f"{self._base}{self._synth_path}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": text,
                    "voiceId": voice,
                    "outputFormat": self._output_format,
                },
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    logger.error(
                        "Uplift TTS API call failed",
                        status_code=resp.status_code,
                    )
                    raise ProviderInvocationError(
                        classify_http_failure("uplift", resp.status_code)
                    )
                async for network_chunk in resp.aiter_bytes():
                    if cancellation_token and cancellation_token.is_cancelled:
                        return
                    audio_buffer.extend(decoder.feed(network_chunk))
                    if decoder.sample_rate:
                        native_rate = decoder.sample_rate
                    if not emitted_first_audio and len(audio_buffer) >= 2:
                        take = len(audio_buffer) - (len(audio_buffer) % 2)
                        part = bytes(audio_buffer[:take])
                        del audio_buffer[:take]
                        emitted_first_audio = True
                        yield TTSChunk(
                            pcm_data=part,
                            native_sample_rate=native_rate,
                            is_final=False,
                        )
                    while len(audio_buffer) >= self.chunk_size_bytes:
                        take = self.chunk_size_bytes - (self.chunk_size_bytes % 2)
                        part = bytes(audio_buffer[:take])
                        del audio_buffer[:take]
                        yield TTSChunk(
                            pcm_data=part,
                            native_sample_rate=native_rate,
                            is_final=False,
                        )
            if len(audio_buffer) % 2:
                audio_buffer = audio_buffer[:-1]
            if audio_buffer:
                yield TTSChunk(
                    pcm_data=bytes(audio_buffer),
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
            logger.error("Uplift TTS exception", error_type=type(exc).__name__)
            await self.aclose()
            raise provider_invocation_error("uplift", exc) from exc
