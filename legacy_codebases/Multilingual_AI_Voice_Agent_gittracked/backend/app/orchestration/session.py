import logging
import asyncio
import contextlib
import time
import json
from pathlib import Path
from typing import Optional, AsyncIterator

from fastapi import WebSocket

from backend.app.transport.audio_receiver import AudioReceiver
from backend.app.transport.audio_sender import AudioSender
from backend.app.services.stt.gladia_service import GladiaService
from backend.app.services.llm.groq_service import GroqService
from backend.app.services.vad.vad_service import VADProcessor
from backend.app.core.state_machine import CallState, CallStateManager
from backend.app.core.config.language_registry import LanguageRegistry
from backend.app.orchestration.language_router import LanguageRouter
from backend.app.services.tts.tts_manager import TTSManager
from backend.app.core.interfaces import Transcript, LanguageProfile
from backend.app.core.config.config import get_settings

logger = logging.getLogger(__name__)

class _SentenceBridge:
    def __init__(self) -> None:
        self._q: asyncio.Queue[Optional[str]] = asyncio.Queue(maxsize=50)

    async def put(self, sentence: str) -> None:
        await self._q.put(sentence)

    async def close(self) -> None:
        await self._q.put(None)

    def __aiter__(self):
        return self._drain()

    async def _drain(self):
        while True:
            item = await self._q.get()
            if item is None:
                return
            yield item


class SessionOrchestrator:
    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        audio_receiver: AudioReceiver,
        audio_sender: AudioSender,
        ws_lock: asyncio.Lock
    ) -> None:
        self.session_id = session_id
        self._ws = websocket
        self._audio_sender = audio_sender
        self._audio_receiver = audio_receiver
        self._ws_lock = ws_lock

        # Setup per-session logging in logs/sessions/<uuid>.log
        self._log_handler = None
        try:
            log_dir = Path("logs/sessions")
            log_dir.mkdir(parents=True, exist_ok=True)
            self._log_file = log_dir / f"{self.session_id}.log"
            self._log_handler = logging.FileHandler(str(self._log_file), encoding="utf-8")
            self._log_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
            self._log_handler.setFormatter(formatter)
            logging.getLogger().addHandler(self._log_handler)
            logger.info(f"[{self.session_id}] Per-session logging file established.")
        except Exception as e:
            logger.error(f"Failed to initialize session logging: {e}")

        # Services
        self._gladia = GladiaService(session_id, audio_receiver, api_key=get_settings().gladia_api_key)
        self._groq = GroqService(session_id)
        
        self._registry = LanguageRegistry()
        self._router = LanguageRouter(self._registry)
        self._tts_manager = TTSManager(self._registry)

        # State Manager
        self._state_manager = CallStateManager(session_id)

        # Local VAD Processor
        settings = get_settings()
        self._vad = VADProcessor(
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end,
            is_agent_speaking_fn=self._is_agent_speaking,
            threshold=settings.vad_threshold,
            energy_threshold=settings.vad_energy_threshold,
            speech_duration_ms=settings.vad_speech_duration_ms,
            silence_duration_ms=settings.vad_silence_ui_ms,  # comfort filler triggered after UI silence
            noise_gate_k=settings.vad_noise_gate_k,
            noise_gate_window=settings.vad_noise_gate_window
        )

        self._current_bridge: Optional[_SentenceBridge] = None
        self._turn_task: Optional[asyncio.Task] = None
        self._llm_task: Optional[asyncio.Task] = None
        self._turn_lock = asyncio.Lock()
        self._barge_in_active = False
        self._filler_task: Optional[asyncio.Task] = None
        
        # Smart Barge-in verification window state variables
        self._in_verification_window = False
        self._speech_start_time = 0.0
        self._speech_end_time = 0.0
        self._verification_task: Optional[asyncio.Task] = None
        
        self._turn_start_time = 0.0
        self._llm_first_token_time = 0.0
        self._stt_start_time = 0.0 
        self._last_partial_time = 0.0
        
        self._closing_session = False
        
        self._groq.on_sentence(self._on_sentence)    
        self._gladia.on_transcript(self._on_transcript)

    def _is_agent_speaking(self) -> bool:
        """Determines if the agent is actively synthesizing or playout queue has not finished."""
        return self._state_manager.state == CallState.SPEAKING or time.time() < self._audio_sender.speaking_until

    async def process_client_audio(self, chunk: bytes) -> None:
        """Feed incoming raw audio directly to the VAD processor."""
        await self._vad.process_audio(chunk)

    async def run(self) -> None:
        await self._gladia.start()
        if getattr(self._gladia, "last_error", None):
            err_msg = str(self._gladia.last_error)
            if "402" in err_msg or "free audio" in err_msg.lower():
                user_msg = "Gladia STT quota limit reached (402 Payment Required). Speech input is offline, but greeting playback is active."
            else:
                user_msg = f"STT Provider Warning: {err_msg}"
            try:
                async with self._ws_lock:
                    await self._ws.send_text(json.dumps({"type": "error", "message": user_msg}))
            except Exception as e:
                logger.warning("[%s] Could not send STT error payload over WS: %s", self.session_id, e)

    def get_last_error(self) -> Optional[Exception]:
        """Retrieve any error stored on the STT provider."""
        return getattr(self._gladia, "last_error", None)

    async def shutdown(self) -> None:
        await self._gladia.stop()

        if self._verification_task and not self._verification_task.done():
            self._verification_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._verification_task

        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._turn_task

        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._llm_task

        await self._audio_sender.flush()
        self._audio_receiver.flush()
        await self._tts_manager.shutdown()
        await self._vad.shutdown()

        # Detach and close session logger
        if self._log_handler:
            try:
                logging.getLogger().removeHandler(self._log_handler)
                self._log_handler.close()
            except Exception as e:
                logger.error(f"Failed to detach session logger: {e}")

    async def trigger_greeting(self) -> None:
        """Proactively triggers the AI greeting on connection."""
        self._state_manager.transition_to(CallState.THINKING)
        
        lang_profile = self._router.current
        greeting_text = "Hello! I am Zara from Vertex Computers. How can I help you today?"
        if lang_profile.code == "ur":
            greeting_text = "السلام علیکم! میں ورٹیکس کمپیوٹرز سے زارا ہوں۔ آج میں آپ کی کیا مدد کر سکتی ہوں؟"
        elif lang_profile.code == "ar":
            greeting_text = "مرحباً! أنا زارا من فيرتكس كمبيوترز. كيف يمكنني مساعدتك اليوم؟"
        elif lang_profile.code == "ms":
            greeting_text = "Hello! Saya Zara dari Vertex Computers. Ada apa yang boleh saya bantu hari ini?"

        logger.info(f"[{self.session_id}] Triggering greeting: '{greeting_text}'")
        self._turn_start_time = time.time()
        
        async with self._turn_lock:
            self._audio_sender.clear_interrupt()
            
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "transcript", "speaker": "ai", "text": greeting_text}))
                
            tts_provider = await self._tts_manager.get_provider(lang_profile.code)
            self._audio_sender.sample_rate_hz = tts_provider.sample_rate_hz
            
            filler_bridge = _SentenceBridge()
            await filler_bridge.put(greeting_text)
            await filler_bridge.close()
            
            async for audio_chunk in tts_provider.stream_audio(filler_bridge, language_code=lang_profile.code):
                if self._state_manager.state == CallState.THINKING:
                    self._state_manager.transition_to(CallState.SPEAKING)
                elif self._state_manager.state == CallState.LISTENING:
                    break
                await self._audio_sender.queue_output_chunk(audio_chunk)
            
            await self._audio_sender.wait_until_drained()
            self._state_manager.transition_to(CallState.LISTENING)

    async def _on_speech_start(self) -> None:
        """Callback: local VAD speech start detected."""
        now = time.time()
        self._speech_start_time = now
        
        # Is the user interrupting the agent's playout?
        if self._state_manager.state in (CallState.THINKING, CallState.SPEAKING) or (now < self._audio_sender.speaking_until):
            logger.info(f"[{self.session_id}] VAD speech onset detected. Entering verification window.")
            
            # Step A: Pause the agent's current output
            self._audio_sender.pause()
            
            # Cancel any existing verification task and start a new validation window
            if self._verification_task and not self._verification_task.done():
                self._verification_task.cancel()
            self._in_verification_window = True
            self._verification_task = asyncio.create_task(self._run_verification_window())

    async def _on_speech_end(self) -> None:
        """Callback: local VAD speech end detected."""
        self._speech_end_time = time.time()
        
        # If we are in the LISTENING state, transition to THINKING and play comfort filler
        if self._state_manager.state == CallState.LISTENING:
            self._state_manager.transition_to(CallState.THINKING)
            if self._filler_task and not self._filler_task.done():
                self._filler_task.cancel()
            self._filler_task = asyncio.create_task(self._send_thinking_filler())

    async def _run_verification_window(self) -> None:
        """
        Listens for a validation window (e.g. 700ms).
        - If sustained speech is confirmed, fully cancel/barge-in.
        - If it was a false alarm, silently resume playout.
        """
        validation_window_s = 0.7
        min_sustained_speech_s = 0.3
        
        try:
            await asyncio.sleep(validation_window_s)
            
            # Check validation criteria
            is_active = self._vad.is_speech_active
            
            # Calculate duration of the current speech segment
            if is_active:
                # Speech is still ongoing, so it's definitely sustained
                speech_duration = time.time() - self._speech_start_time
            else:
                # Speech ended, check how long it lasted
                speech_duration = self._speech_end_time - self._speech_start_time
                
            logger.info(f"[{self.session_id}] VAD Verification: active={is_active}, duration={speech_duration:.3f}s")
            
            if is_active or speech_duration >= min_sustained_speech_s:
                # True Barge-in (Step D)
                logger.info(f"[{self.session_id}] True barge-in confirmed (sustained speech detected).")
                # Resume sender first so it can process control signals properly
                self._audio_sender.resume()
                self._in_verification_window = False
                await self._barge_in()
            else:
                # False Alarm (Step C)
                logger.info(f"[{self.session_id}] False alarm detected (transient noise). Resuming agent playout.")
                self._audio_sender.resume()
                self._in_verification_window = False
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in verification window task: {e}")
            self._audio_sender.resume()
            self._in_verification_window = False

    async def _send_thinking_filler(self) -> None:
        """Dynamic comfort filler generation using warm TTS engine."""
        if self._state_manager.state != CallState.THINKING:
            return
            
        lang_code = self._router.current.code
        filler_text = "Hmm."
        if lang_code == "ur":
            filler_text = "جی۔"
        elif lang_code == "ar":
            filler_text = "أه۔"
        elif lang_code == "ms":
            filler_text = "Ya."

        logger.info(f"[{self.session_id}] Streaming comfort filler: '{filler_text}' for {lang_code}")
        
        try:
            tts_provider = await self._tts_manager.get_provider(lang_code)
            filler_bridge = _SentenceBridge()
            await filler_bridge.put(filler_text)
            await filler_bridge.close()
            
            async for audio_chunk in tts_provider.stream_audio(filler_bridge, language_code=lang_code):
                if self._state_manager.state != CallState.THINKING:
                    break
                await self._audio_sender.queue_output_chunk(audio_chunk)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Failed to stream comfort filler: {e}")

    async def _on_sentence(self, sentence: str) -> None:
        # Check for sign-off termination tag
        if "[END_CALL]" in sentence:
            logger.info(f"[{self.session_id}] [END_CALL] tag intercepted in sentence: '{sentence}'")
            self._closing_session = True
            sentence = sentence.replace("[END_CALL]", "").strip()
            if not sentence:
                return

        if self._llm_first_token_time == 0.0:
            self._llm_first_token_time = time.time()
            llm_latency = (self._llm_first_token_time - self._turn_start_time) * 1000
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "metric", "name": "Groq LLM Latency", "value": f"{llm_latency:.0f} ms"}))

        async with self._ws_lock:
            await self._ws.send_text(json.dumps({"type": "transcript", "speaker": "ai", "text": sentence}))
        
        if self._current_bridge is not None:
            await self._current_bridge.put(sentence)

    async def _on_transcript(self, transcript: Transcript) -> None:
        async with self._turn_lock:
            if transcript.text:
                current_time = time.time()
    
                if self._stt_start_time == 0.0:
                    self._stt_start_time = time.time()
    
                should_send_ui = True
                if not transcript.is_final:
                    if (current_time - self._last_partial_time) < 0.15:
                        should_send_ui = False
                    else:
                        self._last_partial_time = current_time
    
                if should_send_ui:
                    async with self._ws_lock:
                        await self._ws.send_text(json.dumps({
                            "type": "transcript", 
                            "speaker": "user", 
                            "text": transcript.text, 
                            "is_final": transcript.is_final
                        }))
    
            # Backup text-based barge-in logic using speaking watermark
            if transcript.is_final and (self._state_manager.state in (CallState.THINKING, CallState.SPEAKING) or (time.time() < self._audio_sender.speaking_until)):
                cleaned_text = transcript.text.strip()
                word_count = len(cleaned_text.split())
                if word_count > 3:
                    logger.info(f"[{self.session_id}] Text-based Interruption — transcript word limit reached ({word_count} words).")
                    await self._barge_in()
                else:
                    logger.debug(f"[{self.session_id}] Ignored tiny noise during playback: '{cleaned_text}'")
                            
            if not transcript.is_final or not transcript.text:
                return
    
            if self._state_manager.state != CallState.LISTENING:
                if self._state_manager.state == CallState.THINKING and self._turn_task is None:
                    pass
                else:
                    return
                
            self._state_manager.transition_to(CallState.THINKING)
            
            stt_latency = (time.time() - self._stt_start_time) * 1000
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "metric", "name": "Gladia STT Latency", "value": f"{stt_latency:.0f} ms"}))
            
            self._stt_start_time = 0.0
            self._turn_start_time = time.time()
            self._llm_first_token_time = 0.0
            
            # --- Dynamic Language Routing ---
            word_count = len(transcript.text.strip().split())
            lang_profile = self._router.update(transcript.language, word_count)
            # ------------------------------------
            
            # Re-parameterize VAD thresholds on language switch
            settings = get_settings()
            self._vad.update_thresholds(
                threshold=lang_profile.vad_threshold if lang_profile.vad_threshold is not None else settings.vad_threshold,
                speech_duration_ms=lang_profile.vad_speech_duration_ms if lang_profile.vad_speech_duration_ms is not None else settings.vad_speech_duration_ms,
                silence_duration_ms=lang_profile.vad_silence_duration_ms if lang_profile.vad_silence_duration_ms is not None else settings.vad_silence_ui_ms
            )
    
            # If an existing turn task is running (e.g. code-switching race), cancel and await it first
            if self._turn_task and not self._turn_task.done():
                logger.warning(f"[{self.session_id}] Parallel turn task detected. Cancelling existing turn task.")
                self._turn_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._turn_task
                    
            # Pass calculated profile to turn runner
            self._turn_task = asyncio.create_task(self._run_turn(transcript.text, lang_profile))
            self._turn_task.add_done_callback(
                lambda t: logger.error(
                    "[%s] Turn task failed: %s",
                    self.session_id,
                    t.exception()
                ) if not t.cancelled() and t.exception() else None
            )

    async def _barge_in(self) -> None:
        if self._barge_in_active:
            logger.info(f"[{self.session_id}] Barge-in already in progress. Ignoring concurrent request.")
            return
        
        self._barge_in_active = True
        logger.info(f"[{self.session_id}] Barge-in — cancelling active tasks.")
        
        # Reset any active verification window state
        if self._verification_task and not self._verification_task.done():
            self._verification_task.cancel()
        self._audio_sender.resume()
        self._in_verification_window = False
        
        try:
            # 1. Send client-side "wipe buffer" control message first
            with contextlib.suppress(Exception):
                async with self._ws_lock:
                    await self._ws.send_text(json.dumps({"type": "control", "action": "barge_in"}))
            
            # 2. Reset VAD and flush server queue
            self._vad.reset()
            await self._audio_sender.flush()
            
            # 3. Cancel active TTS generation
            self._tts_manager.cancel_active()
            
            # 4. Cancel active LLM, turn, and filler tasks
            if self._filler_task and not self._filler_task.done():
                self._filler_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._filler_task
            self._filler_task = None
            
            if self._llm_task and not self._llm_task.done():
                self._llm_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._llm_task
                    
            if self._turn_task and not self._turn_task.done():
                self._turn_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._turn_task
                    
            self._turn_task = None
        finally:
            self._barge_in_active = False
            
        self._state_manager.transition_to(CallState.LISTENING)

    async def _run_turn(self, user_text: str, lang_profile: LanguageProfile) -> None:
        bridge = _SentenceBridge()
        self._current_bridge = bridge
        was_cancelled = False
        
        async def _llm_job() -> None:
            try:
                await self._groq.generate_reply(user_text, lang_profile)
            finally:
                await bridge.close()

        self._llm_task = asyncio.create_task(_llm_job())
        
        try:
            tts_provider = await self._tts_manager.get_provider(lang_profile.code)
            assert tts_provider.sample_rate_hz == 22050, f"Unsupported sample rate: {tts_provider.sample_rate_hz}"
            self._audio_sender.sample_rate_hz = tts_provider.sample_rate_hz
            
            # Clear sender interrupt event to allow audio to flow
            self._audio_sender.clear_interrupt()
            
            first_audio = True
            async for audio_chunk in tts_provider.stream_audio(bridge, language_code=lang_profile.code):
                if self._state_manager.state == CallState.THINKING:
                    self._state_manager.transition_to(CallState.SPEAKING)
                elif self._state_manager.state == CallState.LISTENING:
                    break

                if first_audio and self._llm_first_token_time > 0:
                    tts_latency = (time.time() - self._llm_first_token_time) * 1000
                    total_latency = (time.time() - self._turn_start_time) * 1000

                    async with self._ws_lock:
                        await self._ws.send_text(json.dumps({"type": "metric", "name": "TTS Latency", "value": f"{tts_latency:.0f} ms"}))
                        await self._ws.send_text(json.dumps({"type": "metric", "name": "Total Response Time", "value": f"{total_latency:.0f} ms", "highlight": True}))
                    first_audio = False
                    
                await self._audio_sender.queue_output_chunk(audio_chunk)
        except asyncio.CancelledError:
            was_cancelled = True
            raise
        finally:
            self._current_bridge = None
            if self._llm_task and not self._llm_task.done():
                self._llm_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._llm_task
            
            if not was_cancelled:
                # Playout completion wait
                try:
                    await asyncio.wait_for(self._audio_sender.wait_until_drained(), timeout=2.0)
                except Exception as e:
                    logger.warning(f"[{self.session_id}] Playout drain timed out or failed: {e}")
            
            # Check if this turn marks the end of the call
            if self._closing_session:
                logger.info(f"[{self.session_id}] Graceful call sign-off. Closing WebSocket connection.")
                with contextlib.suppress(Exception):
                    async with self._ws_lock:
                        await self._ws.send_text(json.dumps({"type": "control", "action": "hangup"}))
                        await self._ws.close()
            else:
                self._state_manager.transition_to(CallState.LISTENING)
                self._turn_task = None
