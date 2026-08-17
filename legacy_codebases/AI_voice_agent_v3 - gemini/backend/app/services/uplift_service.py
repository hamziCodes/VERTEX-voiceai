from __future__ import annotations
import asyncio
import logging
import os
import uuid
from typing import AsyncIterator

from backend.app.core.config.config import get_settings

import aiohttp

logger = logging.getLogger(__name__)

settings = get_settings() #get validated settings from config.py

UPLIFT_API_KEY = settings.uplift_api_key
UPLIFT_VOICE_ID = settings.uplift_voice_id
_SYNTH_URL = "https://api.upliftai.org/v1/synthesis/text-to-speech"

class TTSTimeoutError(RuntimeError): ...
class TTSRateLimitError(RuntimeError): ...
class TTSProviderError(RuntimeError): ...

class UpliftTTSService:
    #configuration for the Uplift TTS service. 
    def __init__(
        self,
        api_key: str = UPLIFT_API_KEY,
        voice_id: str = UPLIFT_VOICE_ID,
        output_format: str = "PCM_22050_16", 
        connect_timeout: float = 3.0,
        sentence_timeout: float = 8.0,
        max_retries: int = 1,
    ) -> None:
        self._voice_id = voice_id
        self._fmt = output_format
        self._max_retries = max_retries
        
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        
        # Connection Pooling. This keeps the network tunnel open between sentences.
        connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=None, connect=connect_timeout, sock_read=sentence_timeout)
        self._session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers=self._headers)
        
        # interrupts the AI if the user starts speaking
        self._cancel_evt = asyncio.Event()

    # flag to stop the tts and detect user audio input
    def cancel(self) -> None:
        """Signal in flight synthesis to abort immediately."""
        self._cancel_evt.set()

    #resets the switch to false at the start of every tts cycle
    def _reset_cancel(self) -> None:
        self._cancel_evt.clear()
    
    #cleanup the connection after application closes
    async def aclose(self) -> None:
        await self._session.close()

    #CORE OF THE TTS SERVICE. This is where the text is sent to the Uplift API and the audio bytes are streamed back.
    async def _synthesize_sentence(self, text: str, request_id: str) -> AsyncIterator[bytes]:
        payload = {"voiceId": self._voice_id, "text": text, "outputFormat": self._fmt}
        attempt = 0
        
        while True:
            attempt += 1
            try:
                async with self._session.post(_SYNTH_URL, json=payload) as resp:
                    # --- 1. RATE LIMIT & ERROR DEFENSE ---
                    # 429 - too many requests - wait using asyniosleep and retry
                    if resp.status == 429:
                        if attempt > self._max_retries:
                            raise TTSRateLimitError(f"[{request_id}] Rate-limited")
                        await asyncio.sleep(float(resp.headers.get("Retry-After", 1.5)))
                        continue

                    # 500+ - server error - wait using exponential backoff and retry    
                    if resp.status >= 500:
                        if attempt > self._max_retries:
                            raise TTSProviderError(f"[{request_id}] Uplift {resp.status}")
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))  #0.5s, 1s, 2s, 4s, 8s, etc retry
                        continue

                    # if not 200 - raise an error with the response body for debugging
                    if resp.status != 200:
                        body = await resp.text()
                        raise TTSProviderError(f"[{request_id}] Uplift Error {resp.status}: {body}")
                    
                    # --- 2. THE CHUNKING ---
                    #send in audio chunks of 4096 instead of waiting for the entire audio to be generated. 
                    async for chunk in resp.content.iter_chunked(4096):
                        if self._cancel_evt.is_set():
                            return  
                        if chunk:
                            yield chunk
                    return

            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                if attempt > self._max_retries:
                    raise TTSProviderError(f"[{request_id}] Transport error: {exc}")
                await asyncio.sleep(0.5 * attempt)

    #connects the LLm to the TTS service and streams the audio back to the user.
    async def stream_audio(self, text_iterator: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """Consumes sentences from the LLM; yields perfectly aligned raw audio bytes."""
        
        self._reset_cancel()
        leftover = b''  
        bytes_to_skip = 2048  #number of bytes to skip for the pop sound

        logger.debug("TTS stream_audio: starting consumption loop.")
        try:
            async for sentence in text_iterator:
                if self._cancel_evt.is_set():
                    logger.debug("TTS stream_audio: cancel event is set, stopping consumption.")
                    return
                    
                sentence = sentence.strip()
                if not sentence: continue
                
                request_id = uuid.uuid4().hex[:8]
                logger.info(f"TTS stream_audio: processing sentence [{request_id}]: '{sentence}'")
                
                try:
                    chunk_count = 0
                    async for audio_chunk in self._synthesize_sentence(sentence, request_id):
                        if self._cancel_evt.is_set():
                            logger.debug(f"TTS stream_audio: cancel event set during synthesis of [{request_id}]")
                            return
                        
                        #cut the pop sounf from the start of the TTS audio stream
                        if bytes_to_skip > 0:
                            if len(audio_chunk) <= bytes_to_skip:
                                bytes_to_skip -= len(audio_chunk)
                                continue #cleard the static move on
                            else:
                                audio_chunk = audio_chunk[bytes_to_skip:]
                                bytes_to_skip = 0 #successfully bypassed pop
                            
                        leftover = leftover + audio_chunk
                        chunk_count += 1
                        
                        # If the combined chunk has an odd number of bytes, 
                        # we yield all but the last byte and save it for the next iteration.
                        if len(leftover) >= 8192:
                            if len(leftover) % 2 != 0:
                                yield leftover[:-1]  #yield all but the last byte
                                leftover = leftover[-1:] 
                            else:
                                yield leftover
                                leftover = b'' 
                    
                    logger.debug(f"TTS stream_audio: completed synthesis of [{request_id}] with {chunk_count} chunks.")
                            
                except Exception as exc:
                    logger.exception(f"TTS stream_audio: error synthesizing sentence [{request_id}] ({sentence}): {exc}")
                    continue
        except Exception as outer_exc:
            logger.exception(f"TTS stream_audio: outer exception in consumption loop: {outer_exc}")
            raise
        
       # Flush any remaining bytes at the end of the turn
        if len(leftover) > 0:
            logger.debug(f"TTS stream_audio: flushing leftover {len(leftover)} bytes.")
            if len(leftover) % 2 != 0:
                yield leftover[:-1]
            else:
                yield leftover