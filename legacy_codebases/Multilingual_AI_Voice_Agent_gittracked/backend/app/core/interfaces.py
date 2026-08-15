"""
Core Interfaces for the Multilingual Voice Agent.

These Protocol classes define strict contracts that every STT, LLM, and TTS
provider must implement. The SessionOrchestrator depends ONLY on these
interfaces—never on concrete vendor implementations—making providers
perfectly interchangeable.

WHY THIS FILE EXISTS:
    Without this, your orchestrator imports GladiaService, GroqService, 
    UpliftTTSService directly. Adding Arabic means editing the orchestrator.
    With this, adding Arabic means adding a config file. The orchestrator
    never changes.

DESIGN DECISIONS:
    - No vendor imports: Transcript is defined here, not imported from Gladia
    - Async callbacks: Orchestrator does async work in callbacks (state changes, 
      task creation), so callbacks must be awaitable
    - Language flows through: Every method that needs language context receives 
      it as a parameter, not from global state
    - Minimal surface area: Only methods the orchestrator actually calls
"""

from typing import AsyncIterator, Callable, Awaitable, Protocol, runtime_checkable
from dataclasses import dataclass
#brick 4
from backend.app.core.config.language_registry import LanguageProfile

# =============================================================================
# SHARED DATA STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class Transcript:
    """
    Universal transcript format produced by EVERY STT provider.
    
    WHY NOT USE GLADIA'S TYPE DIRECTLY?
        Because the whole point of this file is provider-agnosticism.
        If we import GladiaTranscript here, we've defeated the purpose—
        swapping Gladia for Azure would break every downstream consumer.
        
    MIGRATION NOTE:
        Your existing GladiaService._extract_text() currently returns
        GladiaTranscript. You'll add a thin conversion layer there:
        
            def _extract_text(self, msg) -> Transcript:
                # ... existing parsing logic ...
                return Transcript(
                    session_id=self._session_id,
                    text=text,
                    is_final=is_final,
                    language=language,  # Already parsed, just pass it through
                )
    
    Attributes:
        session_id: Unique ID for this transcription session
        text: The transcribed content
        is_final: True = utterance complete, False = still speaking
        language: ISO 639-1 code ("ur", "en", "ar", "ms")
        confidence: Optional 0.0-1.0 score if provider supports it
    """
    session_id: str
    text: str
    is_final: bool
    language: str
    confidence: float | None = None


# Type aliases for readability
TranscriptCallback = Callable[[Transcript], Awaitable[None]]
SentenceCallback = Callable[[str], Awaitable[None]]


# =============================================================================
# STT PROVIDER CONTRACT
# =============================================================================

@runtime_checkable
class STTProvider(Protocol):
    """
    Contract for Speech-to-Text services.
    
    WHAT THE ORCHESTRATOR EXPECTS:
        1. Instantiate (with provider-specific config)
        2. Call on_transcript() to register callback
        3. Call start() to begin the session
        4. Feed audio somehow (NOT in this protocol—varies by provider)
        5. Receive Transcript objects via callback
        6. Call stop() when done
    
    WHY NO AUDIO INPUT METHOD?
        Gladia uses WebSocket push. Azure uses HTTP POST chunks. 
        Deepgram uses gRPC streams. There's no universal signature.
        Each implementation exposes its own audio input method;
        only the output (transcript callback) is standardized.
    
    YOUR CURRENT GLADIASERVICE:
        Already implements 90% of this. Changes needed:
        - Change callback type from your current signature to TranscriptCallback
        - Convert GladiaTranscript → Transcript in _extract_text()
        - Rename stop_recording() → stop() (or add stop() as alias)
    """
    
    async def start(self) -> None:
        """Initialize and begin the live transcription session."""
        ...
    
    async def stop(self) -> None:
        """
        End the session and release resources.
        
        MUST BE IDEMPOTENT: Safe to call multiple times.
        Your existing stop_recording() already does this.
        """
        ...
    
    def on_transcript(self, callback: TranscriptCallback) -> None:
        """
        Register the callback that receives all transcription results.
        
        The callback is invoked for BOTH partial and final transcripts.
        Check transcript.is_final to distinguish.
        
        The callback MUST BE AWAITED by the implementation, not fire-and-forget.
        """
        ...


# =============================================================================
# LLM PROVIDER CONTRACT  
# =============================================================================

@runtime_checkable
class LLMProvider(Protocol):
    """
    Contract for Language Model services.
    
    WHAT THE ORCHESTRATOR EXPECTS:
        1. Instantiate (with API key, model, base prompt, etc.)
        2. Call on_sentence() to register callback
        3. Call generate_reply() with user text + target language
        4. Receive completed sentences via callback (streaming, not batch)
    
    WHY LANGUAGE_CODE IS A PARAMETER:
        The LLM doesn't know what language to reply in unless we tell it.
        This parameter lets the orchestrator pass "ar" when the user just
        spoke Arabic, and the implementation injects the right directive.
        
        Your current GroqService loads ONE prompt at init. After migration,
        it will inject a language directive per-turn based on this parameter.
    
    YOUR CURRENT GROQSERVICE:
        Already implements 90% of this. Changes needed:
        - Add language_code parameter to generate_reply()
        - Load/use language directive inside generate_reply() based on param
        - Change on_sentence callback signature to SentenceCallback
    """
    
    async def generate_reply(
        self, 
        user_text: str, 
        lang_profile: LanguageProfile #brick 4
    ) -> None:
        """
        Generate a streaming reply to the user's utterance.
        
        Results are NOT returned here. Instead, completed sentences
        are pushed to the on_sentence callback as they're generated.
        
        Args:
            user_text: The user's final transcript to respond to
            language_code: ISO 639-1 code ("ur", "en", "ar", "ms")
                          Implementation uses this to select/inject
                          the appropriate language directive.
        """
        ...
    
    def on_sentence(self, callback: SentenceCallback) -> None:
        """
        Register callback for completed sentences.
        
        Sentences are delimited by punctuation: . ? ! ۔ ؟
        (Your existing _is_sentence_end() regex already handles this)
        
        The callback MUST BE AWAITED by the implementation.
        """
        ...


# =============================================================================
# TTS PROVIDER CONTRACT
# =============================================================================

@runtime_checkable
class TTSProvider(Protocol):
    """
    Contract for Text-to-Speech services.
    
    WHAT THE ORCHESTRATOR EXPECTS:
        1. Instantiate (with API key, voice IDs, etc.)
        2. Call stream_audio() with sentence iterator + language code
        3. Consume yielded audio byte chunks
        4. Call cancel() if user barges in
        5. Call aclose() at session end
    
    WHY LANGUAGE_CODE IS A PARAMETER:
        Different languages need different voices. Instead of creating
        a separate TTS instance per language (wasteful), one instance
        can handle multiple languages by looking up the right voice
        internally based on this parameter.
        
        Alternative: Use TTSManager that holds multiple instances and
        routes based on language. Either approach satisfies this protocol.
    
    AUDIO FORMAT CONVENTION (not enforced by protocol, but expected):
        - PCM 16-bit signed integers
        - 16kHz sample rate  
        - Mono (1 channel)
        - Little-endian byte order
        
        This matches what your frontend PCMPlayerProcessor expects.
        If a provider returns a different format, the implementation
        must convert it before yielding.
    
    YOUR CURRENT UPLIFT SERVICE:
        Already implements 90% of this. Changes needed:
        - Add language_code parameter to stream_audio()
        - Add aclose() method (wrap your existing session close logic)
    """
    
    async def stream_audio(
        self, 
        text_iter: AsyncIterator[str], 
        language_code: str
    ) -> AsyncIterator[bytes]:
        """
        Convert sentence stream to audio byte stream.
        
        Args:
            text_iter: Async iterator yielding complete sentences
            language_code: ISO 639-1 code for voice selection
            
        Yields:
            Raw PCM audio byte chunks. Implementations SHOULD buffer
            to reduce WebSocket message frequency (your current 8192-byte
            accumulation pattern is the right approach).
            
        CANCELLATION:
            If cancel() is called while this is running, the generator
            should exit cleanly on its next iteration check.
        """
        ...
    
    def cancel(self) -> None:
        """
        Abort current synthesis immediately.
        
        Called on barge-in. Your existing implementation sets a flag
        that _synthesize_sentence() checks—keep that pattern.
        
        MUST BE SAFE to call when no synthesis is in progress.
        """
        ...
    
    async def aclose(self) -> None:
        """
        Release provider resources (HTTP session, connection pool).
        
        Called ONCE at session teardown, not per-turn.
        Your current UpliftTTSService closes the aiohttp session—
        wrap that in this method.
        """
        ...

    @property
    def sample_rate_hz(self) -> int:
        """The sample rate of the generated audio in Hertz (e.g. 22050)."""
        ...