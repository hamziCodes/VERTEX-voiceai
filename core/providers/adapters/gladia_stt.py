"""UCVE Gladia STT adapter (REST; mock mode without API key)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.types.audio import AudioFrame


class GladiaSTTProvider(BaseSTTProvider):
    """Gladia STT via HTTP. Uses mock finals when PLATFORM_GLADIA_API_KEY unset."""

    def __init__(self, api_key: str | None = None, mock_text: str = "hello") -> None:
        self.api_key = (api_key or os.environ.get("PLATFORM_GLADIA_API_KEY") or "").strip()
        self.mock_text = mock_text
        self._base = "https://api.gladia.io"

    def health_check(self) -> bool:
        return True

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        config: STTConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[Transcript]:
        buf = bytearray()
        async for frame in audio_stream:
            if cancellation_token and cancellation_token.is_cancelled:
                return
            if frame.pcm16:
                buf.extend(frame.pcm16)

        if not self.api_key or os.environ.get("RUN_LIVE_PROVIDERS") != "1":
            yield Transcript(
                text=self.mock_text, is_final=True, confidence=1.0, language=config.language
            )
            return

        # Live Gladia pre-recorded path (simplified)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base}/v2/pre-recorded",
                headers={"x-gladia-key": self.api_key},
                files={"audio": ("audio.wav", bytes(buf), "application/octet-stream")},
                data={"language": config.language},
            )
            resp.raise_for_status()
            data = resp.json()
            text = (
                data.get("result", {})
                .get("transcription", {})
                .get("full_transcript", "")
            ) or data.get("prediction", "") or ""
            yield Transcript(text=text, is_final=True, confidence=1.0, language=config.language)
