from __future__ import annotations
import asyncio
import logging
import base64
from typing import AsyncIterator
import aiohttp

from backend.app.core.config.config import get_settings
from backend.app.core.interfaces import TTSProvider
from backend.app.core.config.language_registry import LanguageRegistry

logger = logging.getLogger(__name__)
settings = get_settings()

# FIX: The correct standard endpoint for short audio synthesis
_GOOGLE_TTS_URL = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={settings.google_tts_api_key}"

# High-quality WaveNet/Neural2 female voices
GOOGLE_VOICES = {
    "en": "en-US-Neural2-F",      
    "ar": "ar-XA-Wavenet-B",       
    "ms": "ms-MY-Wavenet-B",       
}


# Google Cloud TTS requires proper BCP-47 tags
GOOGLE_LANGUAGE_CODES = {
    "en": "en-US",
    "ar": "ar-XA",
    "ms": "ms-MY",
    "ur": "ur-PK",
}

class GoogleTTSService(TTSProvider):
    """Google Cloud TTS using standard synthesis (perfect for short sentences)."""
    
    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or settings.google_tts_api_key
        if not self._api_key or "your_key" in self._api_key.lower():
            logger.error("🚨 GOOGLE_TTS_API_KEY is not configured or contains placeholder in .env!")
            
        self._registry = LanguageRegistry()
        
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=None, connect=3.0, sock_read=8.0)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        self._cancel_evt = asyncio.Event()

    @property
    def sample_rate_hz(self) -> int:
        return 22050

    def cancel(self) -> None:
        self._cancel_evt.set()

    def _reset_cancel(self) -> None:
        self._cancel_evt.clear()
        
    async def aclose(self) -> None:
        await self._session.close()

    async def stream_audio(self, text_iter: AsyncIterator[str], language_code: str = "en") -> AsyncIterator[bytes]:
        self._reset_cancel()
        
        # Determine voice name from profile override or fall back to default map
        profile = self._registry.get(language_code)
        voice_name = profile.tts_voice_id or GOOGLE_VOICES.get(language_code, GOOGLE_VOICES["en"])
        bcp47_code = GOOGLE_LANGUAGE_CODES.get(language_code, "en-US")
        
        headers = {"Content-Type": "application/json; charset=utf-8"}
        leftover = b''  # Persists across sentences
        
        # Construct the URL dynamically to pick up any runtime env/settings changes
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self._api_key}"
        
        async for sentence in text_iter:
            if self._cancel_evt.is_set():
                return
                
            sentence = sentence.strip()
            if not sentence: continue
            
            payload = {
                "input": {"text": sentence},
                "voice": {
                    "languageCode": bcp47_code,
                    "name": voice_name
                },
                "audioConfig": {
                    "audioEncoding": "LINEAR16",   # Raw PCM
                    "sampleRateHertz": 22050,      # Match the frontend config
                    "speakingRate": 1.0
                }
            }
            
            try:
                async with self._session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Google TTS Error {resp.status}: {error_text}")
                        raise RuntimeError(f"Google TTS failed with status {resp.status}: {error_text}")
                        
                    # Google returns JSON with a base64 encoded string for short audio
                    data = await resp.json()
                    audio_b64 = data.get("audioContent", "")
                    
                    if audio_b64:
                        raw_audio = base64.b64decode(audio_b64)
                        # Trim the first 50ms (even-aligned to prevent sample phase shift/static)
                        trim_bytes = int(0.050 * 22050 * 2) & ~1  # 2204 bytes
                        if len(raw_audio) > trim_bytes:
                            raw_audio = raw_audio[trim_bytes:]
                        else:
                            raw_audio = b''
                        leftover = leftover + raw_audio
                        
                        chunk_size = 4096
                        while len(leftover) >= chunk_size:
                            yield leftover[:chunk_size]
                            leftover = leftover[chunk_size:] 
                                
            except Exception as e:
                logger.error(f"Google TTS stream error: {e}")
                raise e
                
        # Flush any remainder after processing all sentences
        if len(leftover) > 0:
            if len(leftover) % 2 != 0:
                yield leftover[:-1]
            else:
                yield leftover