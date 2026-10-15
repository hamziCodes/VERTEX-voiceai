"""UCVE Uplift TTS adapter (mock PCM when key unset)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig
from core.providers.mode import should_use_mock_provider

logger = get_logger("ucve.providers.uplift")


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
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_UPLIFT_API_KEY")
            or os.environ.get("UPLIFT_API_KEY")
            or ""
        ).strip()
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
                preview=text[:80],
            )
            resp = await client.post(
                f"{self._base}{self._synth_path}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "text": text,
                    "voiceId": voice,
                    "outputFormat": self._output_format,
                },
            )
            if resp.status_code != 200:
                logger.error(
                    "Uplift TTS API call failed",
                    status_code=resp.status_code,
                    error=resp.text,
                )
                resp.raise_for_status()
            pcm = resp.content
            # Pop-skip a WAV header if the vendor prepends RIFF (Phase 6).
            if pcm[:4] == b"RIFF" and len(pcm) > 44:
                pcm = pcm[44:]
            skip = max(0, int(os.environ.get("UCVE_TTS_POP_SKIP_BYTES", "0") or 0))
            if skip and len(pcm) > skip:
                pcm = pcm[skip:]
            chunk_size = self.chunk_size_bytes
            fmt = self._output_format.upper()
            if "22050" in fmt:
                native_rate = 22050
            elif "24000" in fmt:
                native_rate = 24000
            elif "16000" in fmt:
                native_rate = 16000
            else:
                native_rate = config.sample_rate
            for i in range(0, len(pcm), chunk_size):
                if cancellation_token and cancellation_token.is_cancelled:
                    return
                yield TTSChunk(
                    pcm_data=pcm[i : i + chunk_size],
                    native_sample_rate=native_rate,
                    is_final=(i + chunk_size >= len(pcm)),
                )
        except Exception as exc:
            logger.error(f"Uplift TTS Exception: {exc}", error=str(exc))
            await self.aclose()
            raise
