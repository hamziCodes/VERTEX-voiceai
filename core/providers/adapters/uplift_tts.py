"""UCVE Uplift TTS adapter (mock PCM when key unset)."""

from __future__ import annotations

import os
import struct
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig


def _tone_pcm(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    """Generate a short silent/near-tone PCM16 buffer for mock egress."""
    n = int(sample_rate * duration_ms / 1000)
    return struct.pack("<" + "h" * n, *([0] * n))


class UpliftTTSProvider(BaseTTSProvider):
    """Uplift TTS REST adapter. Emits mock PCM when PLATFORM_UPLIFT_API_KEY unset."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or os.environ.get("PLATFORM_UPLIFT_API_KEY") or "").strip()
        self._base = os.environ.get("UPLIFT_API_BASE", "https://api.upliftai.org")

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

        if not self.api_key or os.environ.get("RUN_LIVE_PROVIDERS") != "1":
            pcm = _tone_pcm(duration_ms=max(100, min(2000, len(text) * 40)))
            yield TTSChunk(pcm_data=pcm, native_sample_rate=16000, is_final=True)
            return

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/v1/tts",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"text": text, "voice_id": config.voice_id, "encoding": "pcm16"},
            )
            resp.raise_for_status()
            # Assume raw PCM or JSON with base64 — prefer content-type audio
            pcm = resp.content
            yield TTSChunk(
                pcm_data=pcm,
                native_sample_rate=config.sample_rate,
                is_final=True,
            )
