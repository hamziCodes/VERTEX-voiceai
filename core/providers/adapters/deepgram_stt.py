"""UCVE Deepgram STT adapter (HTTP/REST & streaming; mock fallback when API key unset)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.exceptions import (
    ProviderInvocationError,
    classify_http_failure,
    provider_invocation_error,
)
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig, Transcript
from core.providers.mode import provider_is_locally_ready, should_use_mock_provider
from core.types.audio import AudioFrame, pcm16_to_wav

logger = get_logger("ucve.providers.deepgram")

_MIN_PCM_BYTES = 3200  # ~100ms @ 16kHz mono PCM16


class DeepgramSTTProvider(BaseSTTProvider):
    """Deepgram STT adapter for English and multilingual voice streams."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "nova-3",
        mock_text: str = "",
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model = model
        self.mock_text = mock_text
        self._base = "https://api.deepgram.com/v1/listen"

    def health_check(self) -> bool:
        return provider_is_locally_ready(api_key=self.api_key)

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

        use_mock = should_use_mock_provider(
            provider_id="deepgram", api_key=self.api_key
        )
        if use_mock:
            if len(buf) < _MIN_PCM_BYTES:
                return
            text = (self.mock_text or "Hello from Deepgram transcription.").strip()
            yield Transcript(
                text=text,
                is_final=True,
                confidence=0.98,
                language=config.language or "en",
            )
            return

        wav_bytes = pcm16_to_wav(bytes(buf), sample_rate=config.sample_rate)
        if not wav_bytes:
            return

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }
        params = {
            "model": self.model,
            "language": config.language or "en",
            "smart_format": "true",
            "punctuate": "true",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    self._base,
                    content=wav_bytes,
                    headers=headers,
                    params=params,
                )
            if res.status_code != 200:
                logger.error("Deepgram HTTP failure", status=res.status_code)
                raise ProviderInvocationError(
                    classify_http_failure("deepgram", res.status_code)
                )

            data = res.json()
            results = data.get("results", {})
            channels = results.get("channels", [])
            transcript_text = ""
            confidence = 0.95
            if channels:
                alt = channels[0].get("alternatives", [{}])[0]
                transcript_text = alt.get("transcript", "").strip()
                confidence = float(alt.get("confidence", 0.95))

            if transcript_text:
                yield Transcript(
                    text=transcript_text,
                    is_final=True,
                    confidence=confidence,
                    language=config.language,
                )
        except ProviderInvocationError:
            raise
        except Exception as exc:
            logger.error(
                "Deepgram transcription exception", error_type=type(exc).__name__
            )
            raise provider_invocation_error("deepgram", exc) from exc
