import logging
import asyncio
import time
from typing import AsyncIterator

from backend.app.core.interfaces import TTSProvider
from backend.app.services.tts.uplift_service import UpliftTTSService
from backend.app.core.config.language_registry import LanguageRegistry
from backend.app.services.tts.elevenlabs_service import ElevenLabsTTSService
from backend.app.services.tts.google_service import GoogleTTSService

logger = logging.getLogger(__name__)

class ReplayableAsyncIterator:
    """
    Wraps an AsyncIterator to cache all yielded items.
    Allows replaying the cached items from the beginning if needed.
    """
    def __init__(self, iterator: AsyncIterator[str]) -> None:
        self._iterator = iterator.__aiter__()
        self._consumed = []
        self._replay_index = 0
        self._replaying = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if self._replaying:
            if self._replay_index < len(self._consumed):
                val = self._consumed[self._replay_index]
                self._replay_index += 1
                return val
            else:
                self._replaying = False
        
        try:
            val = await self._iterator.__anext__()
            self._consumed.append(val)
            return val
        except StopAsyncIteration:
            raise

    def enable_replay(self) -> None:
        self._replaying = True
        self._replay_index = 0


class FailoverTTSProvider(TTSProvider):
    """
    Wraps primary and fallback providers.
    Intercepts calls and automatically redirects to fallback upon timeouts or consecutive errors.
    """
    def __init__(
        self,
        manager: 'TTSManager',
        primary_provider: TTSProvider,
        primary_name: str,
        fallback_provider: TTSProvider,
        fallback_name: str,
        language_code: str
    ) -> None:
        self.manager = manager
        self.primary_provider = primary_provider
        self.primary_name = primary_name
        self.fallback_provider = fallback_provider
        self.fallback_name = fallback_name
        self.language_code = language_code
        self._active_provider = self.primary_provider
        self._active_name = self.primary_name

    @property
    def sample_rate_hz(self) -> int:
        return self._active_provider.sample_rate_hz

    def cancel(self) -> None:
        self.primary_provider.cancel()
        self.fallback_provider.cancel()

    async def aclose(self) -> None:
        await self.primary_provider.aclose()
        await self.fallback_provider.aclose()

    async def stream_audio(self, text_iter: AsyncIterator[str], language_code: str) -> AsyncIterator[bytes]:
        # If primary is marked unhealthy by the circuit breaker, failover immediately
        if not self.manager.is_healthy(self.primary_name):
            logger.warning(
                f"[TTS-Failover] Primary provider '{self.primary_name}' is marked unhealthy. "
                f"Routing immediately to fallback '{self.fallback_name}'."
            )
            self._active_provider = self.fallback_provider
            self._active_name = self.fallback_name
            async for chunk in self.fallback_provider.stream_audio(text_iter, language_code):
                yield chunk
            return

        # Attempt to stream from primary, fallback on timeout or error
        self._active_provider = self.primary_provider
        self._active_name = self.primary_name
        
        replayable_iter = ReplayableAsyncIterator(text_iter)
        
        try:
            iterator = self.primary_provider.stream_audio(replayable_iter, language_code).__aiter__()
            first_chunk = True
            while True:
                try:
                    # Enforce a timeout: 3.5s for the first chunk to allow for connection TTFB, 1.5s for subsequent chunks
                    timeout_val = 3.5 if first_chunk else 1.5
                    chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_val)
                    first_chunk = False
                    yield chunk
                except StopAsyncIteration:
                    break
            
            # If the stream finished without errors, record success
            self.manager.record_success(self.primary_name)
            
        except (asyncio.TimeoutError, Exception) as exc:
            err_msg = str(exc) if str(exc).strip() else "TimeoutError"
            logger.error(
                f"[TTS-Failover] Primary provider '{self.primary_name}' failed or timed out: {err_msg}. "
                f"Failing over to fallback '{self.fallback_name}'."
            )
            self.manager.record_failure(self.primary_name)
            
            # Signal cancellation to primary provider to free up hanging tasks
            try:
                self.primary_provider.cancel()
            except Exception:
                pass
                
            self._active_provider = self.fallback_provider
            self._active_name = self.fallback_name
            
            # Enable replay of the consumed sentences
            replayable_iter.enable_replay()
            
            # Stream the remaining sentences from fallback
            async for chunk in self.fallback_provider.stream_audio(replayable_iter, language_code):
                yield chunk


class TTSManager:
    """
    The switchboard that holds initialized TTS engines and routes requests.
    Manages warm connections and acts as a circuit breaker failover coordinator.
    """
    def __init__(self, registry: LanguageRegistry):
        self._registry = registry
        
        # Initialize our available providers once per session
        google_service = GoogleTTSService()
        self._providers: dict[str, TTSProvider] = {
            "uplift": UpliftTTSService(),
            "elevenlabs": ElevenLabsTTSService(fallback_provider=google_service),
            "google": google_service,
        }
        self._active_provider: TTSProvider | None = None
        
        # Circuit Breaker Health Tracking
        self._consecutive_failures: dict[str, int] = {k: 0 for k in self._providers}
        self._unhealthy_until: dict[str, float] = {k: 0.0 for k in self._providers}
        
    def is_healthy(self, name: str) -> bool:
        """Check if a provider is marked healthy or if the cooldown has elapsed."""
        if name not in self._unhealthy_until:
            return True
        return time.time() > self._unhealthy_until[name]

    def record_success(self, name: str) -> None:
        """Reset consecutive failure counter on successful request."""
        if name in self._consecutive_failures:
            self._consecutive_failures[name] = 0

    def record_failure(self, name: str) -> None:
        """Increment consecutive failures. Trips circuit breaker if threshold is hit."""
        if name in self._consecutive_failures:
            self._consecutive_failures[name] += 1
            logger.warning(f"[TTS-Manager] Provider '{name}' failure count: {self._consecutive_failures[name]}")
            if self._consecutive_failures[name] >= 2:
                # Cooldown period of 60 seconds
                self._unhealthy_until[name] = time.time() + 60.0
                logger.error(f"[TTS-Manager] Circuit Breaker: Provider '{name}' tripped! Marked UNHEALTHY for 60s.")

    def _get_fallback_name(self, name: str, language_code: str) -> str:
        """Returns the fallback provider name based on the language."""
        from backend.app.core.config.config import get_settings
        settings = get_settings()
        
        if language_code == "ur":
            if name == "uplift":
                return "google"
            return "uplift"
        else:
            # For English (en), Arabic (ar), Malay (ms)
            if name == "google":
                # Only fallback to elevenlabs if the api key is set and not a placeholder
                if settings.elevenlabs_api_key and "your_key" not in settings.elevenlabs_api_key.lower():
                    return "elevenlabs"
                return "google"
            return "google"
        
    async def get_provider(self, language_code: str) -> TTSProvider:
        """Returns the correct TTS engine wrapper for the requested language."""
        profile = self._registry.get(language_code)
        primary_name = profile.tts_provider
        
        if primary_name not in self._providers:
            logger.warning(f"TTS Provider '{primary_name}' requested for {language_code}, but not initialized. Falling back to 'google'.")
            primary_name = "google"

        fallback_name = self._get_fallback_name(primary_name, language_code)
        
        primary_provider = self._providers[primary_name]
        fallback_provider = self._providers[fallback_name]
        
        failover_provider = FailoverTTSProvider(
            manager=self,
            primary_provider=primary_provider,
            primary_name=primary_name,
            fallback_provider=fallback_provider,
            fallback_name=fallback_name,
            language_code=language_code
        )
        self._active_provider = failover_provider
        return failover_provider

    def cancel_active(self) -> None:
        """Triggered during a user barge-in to stop the current audio."""
        if self._active_provider:
            self._active_provider.cancel()

    async def shutdown(self) -> None:
        """Cleanly close all warm TTS engines on disconnect."""
        for name, provider in self._providers.items():
            if hasattr(provider, 'aclose'):
                await provider.aclose()