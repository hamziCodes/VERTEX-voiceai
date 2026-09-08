"""UCVE Cartesia TTS adapter (PCM bytes; mock when key unset)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.interfaces.tts import BaseTTSProvider, TTSChunk, TTSConfig

logger = get_logger("ucve.providers.cartesia")

# Habiba Phase 6c seeded default (livekit-plugins-cartesia constructor default).
_DEFAULT_VOICE = "f786b574-daa5-4673-aa0c-cbe3e8534c02"
_API = "https://api.cartesia.ai/tts/bytes"
_VERSION = "2025-04-16"


def _tone_pcm(duration_ms: int = 200, sample_rate: int = 16000) -> bytes:
    import math
    import struct

    n = int(sample_rate * duration_ms / 1000)
    out = bytearray()
    for i in range(n):
        sample = int(5500 * math.sin(2 * math.pi * 523.25 * i / sample_rate))
        out.extend(struct.pack("<h", sample))
    return bytes(out)


class CartesiaTTSProvider(BaseTTSProvider):
    """Cartesia Sonic TTS → raw PCM16 (English-friendly, cheaper debug alternative)."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        chunk_size_bytes: int = 3200,
    ) -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_CARTESIA_API_KEY")
            or os.environ.get("CARTESIA_API_KEY")
            or ""
        ).strip()
        self.chunk_size_bytes = max(320, int(chunk_size_bytes))
        self._model = os.environ.get("CARTESIA_MODEL_ID", "sonic-2")
        self._sample_rate = int(os.environ.get("CARTESIA_SAMPLE_RATE", "16000") or 16000)
        self._version = os.environ.get("CARTESIA_VERSION", _VERSION)
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
            os.environ.get("CARTESIA_VOICE_ID")
            or os.environ.get("PLATFORM_CARTESIA_VOICE_ID")
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

        cleaned = (text or "").strip()
        # Skip punctuation-only scraps (e.g. Urdu full stop "۔") — Cartesia 400s on these.
        if not cleaned or not any(ch.isalnum() for ch in cleaned):
            logger.info("Skipping Cartesia TTS for empty/punctuation text", preview=cleaned[:20])
            return

        use_mock = (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
        )
        if use_mock:
            if not self.api_key:
                logger.info("Cartesia TTS API key not set — using Mock TTS provider.")
            pcm = _tone_pcm(duration_ms=max(100, min(2000, len(cleaned) * 40)))
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
        sample_rate = int(config.sample_rate or self._sample_rate or 16000)
        # Basic script hint: Arabic-range → ur, else en.
        language = "ur" if any("\u0600" <= ch <= "\u06FF" for ch in cleaned) else "en"
        payload = {
            "model_id": self._model,
            "transcript": cleaned,
            "voice": {"mode": "id", "id": voice},
            "language": language,
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": sample_rate,
            },
        }
        logger.info(
            "Initiating Cartesia TTS synthesis request",
            text_len=len(cleaned),
            voice_id=voice,
            model_id=self._model,
            sample_rate=sample_rate,
            language=language,
            preview=cleaned[:80],
        )
        client = self._get_client()
        try:
            async with client.stream(
                "POST",
                _API,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Cartesia-Version": self._version,
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error(
                        "Cartesia TTS API call failed",
                        status_code=resp.status_code,
                        error=body[:300].decode("utf-8", errors="replace"),
                    )
                    resp.raise_for_status()

                buf = bytearray()
                async for raw in resp.aiter_bytes():
                    if cancellation_token and cancellation_token.is_cancelled:
                        return
                    if not raw:
                        continue
                    buf.extend(raw)
                    while len(buf) >= self.chunk_size_bytes:
                        take = self.chunk_size_bytes - (self.chunk_size_bytes % 2)
                        part = bytes(buf[:take])
                        del buf[:take]
                        yield TTSChunk(
                            pcm_data=part,
                            native_sample_rate=sample_rate,
                            is_final=False,
                        )
                if buf:
                    if len(buf) % 2 == 1:
                        buf = buf[:-1]
                    if buf:
                        yield TTSChunk(
                            pcm_data=bytes(buf),
                            native_sample_rate=sample_rate,
                            is_final=True,
                        )
                else:
                    yield TTSChunk(
                        pcm_data=b"",
                        native_sample_rate=sample_rate,
                        is_final=True,
                    )
        except Exception as exc:
            logger.error("Cartesia TTS Exception: {0}".format(exc), error=str(exc))
            await self.aclose()
            raise
