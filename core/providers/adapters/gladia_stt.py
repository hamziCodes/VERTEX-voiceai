"""UCVE Gladia STT adapter (REST; mock mode without API key)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.types.audio import AudioFrame, pcm16_to_wav


from core.observability.logging import get_logger

logger = get_logger("ucve.providers.gladia")

_MIN_PCM_BYTES = 3200  # ~100ms @ 16kHz mono PCM16


class GladiaSTTProvider(BaseSTTProvider):
    """Gladia STT via HTTP. Uses mock finals when GLADIA_API_KEY unset."""

    def __init__(self, api_key: str | None = None, mock_text: str = "") -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_GLADIA_API_KEY")
            or os.environ.get("GLADIA_API_KEY")
            or ""
        ).strip()
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
        _MAX_BUF = 512 * 1024
        async for frame in audio_stream:
            if cancellation_token and cancellation_token.is_cancelled:
                return
            if frame.pcm16:
                if len(buf) + len(frame.pcm16) > _MAX_BUF:
                    break
                buf.extend(frame.pcm16)

        use_mock = (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
        )
        if use_mock:
            # Fix "hello" loop: never fabricate a transcript for a false/short
            # VAD trigger, and only emit mock text when explicitly configured.
            if len(buf) < _MIN_PCM_BYTES or not self.mock_text:
                if not self.api_key:
                    logger.info("Gladia STT (mock) — no transcript for short/empty buffer.")
                return
            yield Transcript(
                text=self.mock_text, is_final=True, confidence=1.0, language=config.language
            )
            return

        if len(buf) < _MIN_PCM_BYTES:
            logger.warning("Gladia STT skipped — utterance too short", pcm_bytes=len(buf))
            return

        wav_bytes = pcm16_to_wav(bytes(buf), sample_rate=16000, channel_count=1)
        if not wav_bytes:
            return

        try:
            logger.info("Initiating Gladia STT pre-recorded request", pcm_bytes=len(buf))
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self._base}/v2/pre-recorded",
                    headers={"x-gladia-key": self.api_key},
                    files={"audio": ("audio.wav", wav_bytes, "audio/wav")},
                    data={"language": config.language},
                )
                if resp.status_code != 200 and resp.status_code != 201:
                    logger.error(
                        "Gladia API call failed",
                        status_code=resp.status_code,
                        error=resp.text,
                    )
                    resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("result", {})
                    .get("transcription", {})
                    .get("full_transcript", "")
                ) or data.get("prediction", "") or ""
                yield Transcript(text=text, is_final=True, confidence=1.0, language=config.language)
        except Exception as exc:
            logger.error(f"Gladia STT Exception: {exc}", error=str(exc))
            yield Transcript(
                text=self.mock_text, is_final=True, confidence=0.5, language=config.language
            )
