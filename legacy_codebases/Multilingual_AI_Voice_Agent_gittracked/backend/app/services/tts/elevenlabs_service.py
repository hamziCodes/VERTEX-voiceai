from __future__ import annotations
import asyncio
import logging
from typing import AsyncIterator
import aiohttp

from backend.app.core.config.config import get_settings
from backend.app.core.interfaces import TTSProvider

logger = logging.getLogger(__name__)
settings = get_settings()

_ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

class ElevenLabsTTSService(TTSProvider):
    """Multilingual TTS Provider outputting raw PCM to match Uplift."""
    
    def __init__(self, api_key: str | None = None, fallback_provider: TTSProvider | None = None):
        self._api_key = api_key or settings.elevenlabs_api_key
        self._active_voice_id: str | None = None
        self._fallback_provider = fallback_provider
        
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=None, connect=3.0, sock_read=8.0)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        
        self._cancel_evt = asyncio.Event()

    @property
    def sample_rate_hz(self) -> int:
        return 22050

    def cancel(self) -> None:
        self._cancel_evt.set()
        if self._fallback_provider:
            self._fallback_provider.cancel()

    def _reset_cancel(self) -> None:
        self._cancel_evt.clear()
        
    async def aclose(self) -> None:
        await self._session.close()

    async def stream_audio(self, text_iter: AsyncIterator[str], language_code: str = "en") -> AsyncIterator[bytes]:
        self._reset_cancel()
        voice_id = self._active_voice_id or "pNInz6obpgDQGcFmaJgB" 
        
        # THE FIX: Moved leftover outside the loop so it persists across sentences!
        leftover = b''
        
        async for sentence in text_iter:
            if self._cancel_evt.is_set():
                return
                
            sentence = sentence.strip()
            if not sentence: continue
            
            url = _ELEVENLABS_API_URL.format(voice_id=voice_id)
            headers = {
                "xi-api-key": self._api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "text": sentence,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                "output_format": "pcm_22050" 
            }
            
            try:
                async with self._session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"ElevenLabs Error {resp.status}: {error_text}")
                        if self._fallback_provider:
                            logger.warning("ElevenLabs failed. Falling back to Google TTS for this sentence.")
                            async def single_sentence_iter():
                                yield sentence
                            async for fallback_chunk in self._fallback_provider.stream_audio(single_sentence_iter(), language_code=language_code):
                                yield fallback_chunk
                        continue
                        
                    # Trim the first 50ms (even-aligned to prevent sample phase shift/static)
                    bytes_to_skip = int(0.050 * 22050 * 2) & ~1  # 2204 bytes
                    async for chunk in resp.content.iter_chunked(4096):
                        if self._cancel_evt.is_set():
                            return
                        if chunk:
                            if bytes_to_skip > 0:
                                if len(chunk) <= bytes_to_skip:
                                    bytes_to_skip -= len(chunk)
                                    continue
                                else:
                                    chunk = chunk[bytes_to_skip:]
                                    bytes_to_skip = 0
                            
                            leftover = leftover + chunk
                            
                            if len(leftover) >= 8192:
                                if len(leftover) % 2 != 0:
                                    yield leftover[:-1]
                                    leftover = leftover[-1:] 
                                else:
                                    yield leftover
                                    leftover = b'' 
                                    
            except Exception as e:
                logger.error(f"ElevenLabs stream error: {e}")
                continue
        
        if len(leftover) > 0:
            if len(leftover) % 2 != 0:
                yield leftover[:-1]
            else:
                yield leftover