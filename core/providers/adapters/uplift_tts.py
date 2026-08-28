"""UCVE Uplift TTS adapter (mock PCM when key unset)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig


from core.observability.logging import get_logger

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

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_UPLIFT_API_KEY")
            or os.environ.get("UPLIFT_API_KEY")
            or ""
        ).strip()
        self._base = os.environ.get("UPLIFT_API_BASE", "https://api.upliftai.org")
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

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[TTSChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        use_mock = (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
        )
        if use_mock:
            if not self.api_key:
                logger.info("Uplift TTS API key not set — using Mock TTS provider.")
            pcm = _tone_pcm(duration_ms=max(100, min(2000, len(text) * 40)))
            chunk_size = 3200
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
            logger.info("Initiating Uplift TTS synthesis request", text_len=len(text))
            resp = await client.post(
                f"{self._base}/v1/tts",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"text": text, "voice_id": config.voice_id, "encoding": "pcm16"},
            )
            if resp.status_code != 200:
                logger.error(
                    "Uplift TTS API call failed",
                    status_code=resp.status_code,
                    error=resp.text,
                )
                resp.raise_for_status()
            pcm = resp.content
            chunk_size = 3200
            for i in range(0, len(pcm), chunk_size):
                if cancellation_token and cancellation_token.is_cancelled:
                    return
                yield TTSChunk(
                    pcm_data=pcm[i : i + chunk_size],
                    native_sample_rate=config.sample_rate,
                    is_final=(i + chunk_size >= len(pcm)),
                )
        except Exception as exc:
            logger.error(f"Uplift TTS Exception: {exc}", error=str(exc))
            await self.aclose()
            raise
