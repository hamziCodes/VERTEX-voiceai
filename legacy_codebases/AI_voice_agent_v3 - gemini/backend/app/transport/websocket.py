import uuid # used for generating unique identifiers for WebSocket connections
import logging
import asyncio
import contextlib
import time
import json
import enum
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.transport.connection_manager import connection_manager
from backend.app.transport.audio_receiver import AudioReceiver
from backend.app.transport.audio_sender import AudioSender

# Import our three AI services
from backend.app.services.gladia_service import GladiaService, GladiaTranscript
from backend.app.services.gemini_service import GeminiService
from backend.app.services.uplift_service import UpliftTTSService
from backend.app.services.silero_service import SileroVADService

from backend.app.core.config.config import get_settings
from backend.app.core.logging_config import attach_session_log, detach_session_log

router = APIRouter()
logger = logging.getLogger(__name__)

class CallState(enum.Enum):
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"

#handle the LLM and TTS variation in speed and style
class _SentenceBridge:
    """Acts as a conveyor belt between Gemini (pushing text) and Uplift (pulling text)."""
    def __init__(self) -> None:
        self._q: asyncio.Queue[Optional[str]] = asyncio.Queue()

    #LLM pushes sentences into the queue
    async def put(self, sentence: str) -> None:
        await self._q.put(sentence)

    #LLM puts a NONE on the queue to signal TTS that the turn is over
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

# the brain - wires the STT -> LLM -> TTS pipeline together and handles barge-in interruptions
class SessionOrchestrator:
    """The Brain: Manages STT -> LLM -> TTS flow and handles interruptions."""

    def __init__(self, session_id: str, websocket: WebSocket, audio_receiver: AudioReceiver, audio_sender: AudioSender, ws_lock: asyncio.Lock, interrupt_event: asyncio.Event = None) -> None:
        self.session_id = session_id
        self._ws = websocket
        self._audio_sender = audio_sender
        self._audio_receiver = audio_receiver
        self._ws_lock = ws_lock

        #initialize the pipeline services
        self._gladia = GladiaService(session_id, audio_receiver, api_key=get_settings().gladia_api_key)
        self._gemini = GeminiService(session_id)
        self._uplift = UpliftTTSService()
        self._vad = SileroVADService()

        self._current_bridge: Optional[_SentenceBridge] = None
        self._turn_task: Optional[asyncio.Task] = None
        self._llm_task: Optional[asyncio.Task] = None

        self._state = CallState.LISTENING
        # Use the externally-shared event if provided, else create a local one.
        # The shared event must be the same object as AudioSender's so that
        # barge-in signals propagate to the send loop instantly.
        self._interrupt_event = interrupt_event if interrupt_event is not None else asyncio.Event()

        # Initialize the VAD queue and background worker task variables
        self._vad_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        self._vad_task: Optional[asyncio.Task] = None

        # Tracks epoch time until which the client is actively playing audio
        self._speaking_until = 0.0

        # Graceful self-termination flags
        self._closing_session = False

        #initialise telemetery trackers
        self._turn_start_time = 0.0
        self._llm_first_token_time = 0.0
        self._stt_start_time = 0.0 
        self._last_partial_time = 0.0
        #wire up the callbacks
        self._gemini.on_sentence(self._on_sentence)    
        self._gladia.on_transcript(self._on_transcript)

    def is_closing(self) -> bool:
        return self._closing_session

    async def run(self) -> None:
        self._vad_task = asyncio.create_task(self._vad_worker())
        # Start the proactive greeting in the background, registered as _turn_task so it is cancellable on barge-in
        self._turn_task = asyncio.create_task(self.trigger_greeting())
        # Start listening to the mic via Gladia
        try:
            await self._gladia.start()
        except Exception as e:
            logger.error("[%s] Gladia STT initialization/execution failed: %s", self.session_id, e)
            with contextlib.suppress(Exception):
                async with self._ws_lock:
                    await self._ws.send_text(json.dumps({
                        "type": "error",
                        "message": "STT connection failed (Gladia 429 concurrent sessions limit). Please refresh in 30 seconds."
                    }))
            raise 

    async def trigger_greeting(self) -> None:
        """Sends the initial greeting directly to TTS and streams it to the user."""
        greeting_text = "میں فنوا کمپیوٹرز سے زارا ہوں، آج میں آپ کی کیسے مدد کر سکتی ہوں؟"
        logger.info(f"[{self.session_id}] Triggering proactive agent greeting: {greeting_text}")
        
        # 1. Update state to SPEAKING to reflect agent is speaking
        self._state = CallState.SPEAKING
        self._interrupt_event.clear()
        
        # Create a single-sentence iterator for the TTS stream
        async def text_generator():
            yield greeting_text

        # Safely send the AI transcript for the greeting to the client
        try:
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "transcript", "speaker": "ai", "text": greeting_text}))
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to send greeting transcript: {e}")
            
        try:
            chunk_count = 0
            async for audio_chunk in self._uplift.stream_audio(text_generator()):
                if self._interrupt_event.is_set():
                    logger.info(f"[{self.session_id}] Greeting TTS loop broken on interrupt")
                    break
                chunk_count += 1
                await self._audio_sender.queue_output_chunk(audio_chunk)
                
                # mono 16-bit PCM @ 22050Hz has exactly 2 bytes per sample
                chunk_duration = len(audio_chunk) / 2 / 22050
                self._speaking_until = max(self._speaking_until, time.time()) + chunk_duration

            await self._audio_sender.wait_until_drained()
        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Greeting task cancelled due to barge-in/interruption.")
        except Exception as e:
            logger.exception(f"[{self.session_id}] Error streaming greeting: {e}")
        finally:
            # Clean transition to LISTENING if state is still SPEAKING and not interrupted
            if self._state == CallState.SPEAKING:
                self._state = CallState.LISTENING
            self._vad.reset()

    def _flush_vad(self) -> None:
        """Clears all pending audio frames from the VAD queue and resets VAD state."""
        drained = 0
        while not self._vad_queue.empty():
            try:
                self._vad_queue.get_nowait()
                self._vad_queue.task_done()
                drained += 1
            except (asyncio.QueueEmpty, ValueError):
                break
        if drained > 0:
            logger.info(f"[{self.session_id}] Flushed {drained} pending frames from VAD queue at turn start.")
        self._vad.reset()

    async def shutdown(self) -> None:
        if self._vad_task and not self._vad_task.done():
            self._vad_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._vad_task

        await self._gladia.stop_recording()

        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._turn_task

        await self._audio_sender.flush()
        self._audio_receiver.flush()

        await self._uplift.aclose()

    #LLM pushes sentences into the bridge
    async def _on_sentence(self, sentence: str) -> None:
        if self._interrupt_event.is_set():
            logger.debug(f"[{self.session_id}] Interrupt active — dropping lingering Gemini text.")
            return

        # Intercept the graceful self-termination tag
        if "[END_CALL]" in sentence:
            logger.info(f"[{self.session_id}] Intercepted [END_CALL] tag. Activating closing sequence.")
            self._closing_session = True
            sentence = sentence.replace("[END_CALL]", "").strip()

        # If sentence is empty (meaning it only contained [END_CALL]), we skip sending it to the client & TTS
        if not sentence:
            logger.info(f"[{self.session_id}] Empty sentence chunk after stripping [END_CALL] tag.")
            return

        try:
            # 1. Calculate LLM Latency on the very first text generation
            if self._llm_first_token_time == 0.0:
                self._llm_first_token_time = time.time()
                llm_latency = (self._llm_first_token_time - self._turn_start_time) * 1000
                
                async with self._ws_lock:
                    await self._ws.send_text(json.dumps({"type": "metric", "name": "Gemini LLM Latency", "value": f"{llm_latency:.0f} ms"}))

            # 2. Safely send the AI transcript
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "transcript", "speaker": "ai", "text": sentence}))
        except Exception as ws_err:
            logger.error(f"[{self.session_id}] Error sending sentence metadata/transcript to WebSocket: {ws_err}")
        
        if self._current_bridge is not None:
            await self._current_bridge.put(sentence)

     #STT pushes transcripts into the bridge and handles barge-in
    async def _on_transcript(self, transcript: GladiaTranscript) -> None:
        if self._closing_session:
            logger.debug(f"[{self.session_id}] Ignoring transcript during active closing session.")
            return

        #instantly interrupt on partial speech
        if transcript.text:
            current_time = time.time()

            #start STT timer on the very first partial transcript
            if self._stt_start_time == 0.0:
                self._stt_start_time = time.time()

            #throttle partial UI updates to 1 per 150ms
            should_send_ui = True
            if not transcript.is_final:
                if (current_time - self._last_partial_time) < 0.15:
                    should_send_ui = False
                else:
                    self._last_partial_time = current_time

           # Safely send the User transcript
            if should_send_ui:
                async with self._ws_lock:
                    await self._ws.send_text(json.dumps({
                        "type": "transcript", 
                        "speaker": "user", 
                        "text": transcript.text, 
                        "is_final": transcript.is_final
                    }))
                            
        if not transcript.is_final or not transcript.text:
            return

        # Check if the agent is still physically speaking according to the watermark.
        # If so, this transcript belongs to a barge-in, which will be handled by the VAD.
        # We return early to prevent starting a new turn while old audio plays.
        if time.time() < self._speaking_until:
            logger.info(f"[{self.session_id}] Ignoring final transcript during speaking_until window (barge-in VAD handles it)")
            return

        #race Guard
        if self._state != CallState.LISTENING:
            return  # Another turn already claimed the transition
            
        self._state = CallState.THINKING
        
        # Calculate latency and trigger turn
        stt_latency = (time.time() - self._stt_start_time) * 1000
        async with self._ws_lock:
            await self._ws.send_text(json.dumps({"type": "metric", "name": "Gladia STT Latency", "value": f"{stt_latency:.0f} ms"}))
        
        self._stt_start_time = 0.0
        self._turn_start_time = time.time()
        self._llm_first_token_time = 0.0
        
        def handle_turn_result(task: asyncio.Task):
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception(f"[{self.session_id}] Turn task failed with exception: {e}")
        
        self._turn_task = asyncio.create_task(self._run_turn(transcript.text))
        self._turn_task.add_done_callback(handle_turn_result)

    async def _barge_in(self) -> None:
        t0 = time.time()
        logger.info(f"[{self.session_id}] [BARGE-IN] start t={t0:.3f}")
        
        # 1. Set interruption flags immediately
        self._interrupt_event.set()
        self._uplift.cancel()
        logger.info(f"[{self.session_id}] [BARGE-IN] flags set +{(time.time()-t0)*1000:.1f}ms")
        
        # 2. Cancel active tasks immediately and await their completion to prevent race conditions
        if self._llm_task and not self._llm_task.done():
            self._llm_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._llm_task
        if self._turn_task and not self._turn_task.done():
            self._turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._turn_task
        logger.info(f"[{self.session_id}] [BARGE-IN] tasks cancelled and fully cleaned up +{(time.time()-t0)*1000:.1f}ms")
                
        # 3. Flush any remaining audio on the server synchronously
        drained = await self._audio_sender.flush()
        logger.info(f"[{self.session_id}] [BARGE-IN] flushed {drained} chunks +{(time.time()-t0)*1000:.1f}ms")
        
        # 4. Tell the frontend UI to wipe its audio buffer instantly
        with contextlib.suppress(Exception):
            async with self._ws_lock:
                await self._ws.send_text(json.dumps({"type": "control", "action": "barge_in"}))
        logger.info(f"[{self.session_id}] [BARGE-IN] control msg sent +{(time.time()-t0)*1000:.1f}ms  <<< COMPARE THIS TO BROWSER RECEIVE TIME")
            
        # 5. Reset state back to listening
        self._speaking_until = 0.0
        self._state = CallState.LISTENING
        self._vad.reset()

    async def _vad_worker(self) -> None:
        """Single-consumer VAD loop — runs inference off the event loop thread."""
        loop = asyncio.get_running_loop()
        while True:
            chunk = await self._vad_queue.get()
            if self._closing_session:
                self._vad_queue.task_done()
                continue

            t_recv = time.time()
            try:
                # Run PyTorch inference in a background executor thread to avoid blocking the event loop
                triggered = await loop.run_in_executor(None, self._vad.feed, chunk)
            except Exception as e:
                logger.error(f"[{self.session_id}] VAD inference error: {e}")
                continue
            finally:
                self._vad_queue.task_done()
            t_done = time.time()
            # logger.info(f"[{self.session_id}] VAD infer took {(t_done-t_recv)*1000:.1f}ms, triggered={triggered}, state={self._state}")
            if triggered and (self._state in (CallState.THINKING, CallState.SPEAKING) or time.time() < self._speaking_until):
                logger.info(f"[{self.session_id}] BARGE-IN FIRING at t={t_done:.3f} (speaking_until gap={self._speaking_until - time.time():.2f}s)")
                await self._barge_in()

    async def handle_raw_audio(self, data: bytes) -> None:
        """Non-blocking enqueue — never stalls the WS receive loop."""
        try:
            self._vad_queue.put_nowait(data)
        except asyncio.QueueFull:
            with contextlib.suppress(asyncio.QueueEmpty):
                self._vad_queue.get_nowait()
            self._vad_queue.put_nowait(data)

    async def _run_turn(self, user_text: str) -> None:
        """The main loop for a single conversation turn."""
        self._flush_vad()

        bridge = _SentenceBridge()
        self._current_bridge = bridge

        self._state = CallState.THINKING
        self._interrupt_event.clear()

        async def _llm_job() -> None:
            try:
                await self._gemini.generate_reply(user_text)
            finally:
                await bridge.close()

        #start Gemini thinking in the background
        self._llm_task = asyncio.create_task(_llm_job())
        
        try:
            first_audio = True
            chunk_count = 0
            #stream the generated audio chunks directly to the frontend sender
            async for audio_chunk in self._uplift.stream_audio(bridge):
                # Abort streaming immediately if a barge-in event was set
                if self._interrupt_event.is_set():
                    logger.info(f"[{self.session_id}] TTS loop broke on interrupt, chunk #{chunk_count}")
                    break
                chunk_count += 1

                # 4. Calculate TTS and Total Pipeline Latency on the first audio byte
                if first_audio and self._llm_first_token_time > 0:
                    self._state = CallState.SPEAKING
                    tts_latency = (time.time() - self._llm_first_token_time) * 1000
                    total_latency = (time.time() - self._turn_start_time) * 1000

                    async with self._ws_lock:
                        await self._ws.send_text(json.dumps({"type": "metric", "name": "Uplift TTS Latency", "value": f"{tts_latency:.0f} ms"}))
                        await self._ws.send_text(json.dumps({"type": "metric", "name": "Total Response Time", "value": f"{total_latency:.0f} ms", "highlight": True}))
                    first_audio = False
                    
                await self._audio_sender.queue_output_chunk(audio_chunk)
                
                # mono 16-bit PCM @ 22050Hz has exactly 2 bytes per sample
                chunk_duration = len(audio_chunk) / 2 / 22050
                self._speaking_until = max(self._speaking_until, time.time()) + chunk_duration

                logger.debug(f"[{self.session_id}] queued chunk #{chunk_count} at t={time.time():.3f} (speaking_until offset={self._speaking_until - time.time():.2f}s)")

            # Wait until the outgoing audio queue has been completely drained (sent to client)
            # before we transition the state back to LISTENING. This ensures self._state
            # remains CallState.SPEAKING throughout the entire duration of the audio playback.
            await self._audio_sender.wait_until_drained()

            if self._closing_session:
                play_remaining = self._speaking_until - time.time()
                if play_remaining > 0:
                    logger.info(f"[{self.session_id}] Waiting {play_remaining:.2f}s for final goodbye to finish playing.")
                    await asyncio.sleep(play_remaining)
                logger.info(f"[{self.session_id}] Playout complete. Closing WebSocket session gracefully.")
                async with self._ws_lock:
                    await self._ws.close(code=1000, reason="Conversation completed")
        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Turn task cancelled gracefully.")
        except Exception as e:
            logger.exception(f"[{self.session_id}] Exception occurred in turn execution loop: {e}")
        finally:
            self._current_bridge = None
            if self._llm_task and not self._llm_task.done():
                self._llm_task.cancel()

                with contextlib.suppress(asyncio.CancelledError):
                    await self._llm_task
            
            # Reset state back to LISTENING if it hasn't been claimed by a concurrent barge-in
            if self._state in (CallState.SPEAKING, CallState.THINKING):  
                self._state = CallState.LISTENING

@router.websocket("/ws/audio") # this is the endpoint for WebSocket connection
async def audio_endpoint(websocket: WebSocket):
    #establish a unique session ID for this caller
    session_id = str(uuid.uuid4())

    # Everything logged during this call — from ANY module, including the VAD
    # frame-by-frame dump — gets mirrored into logs/sessions/<session_id>.log.
    # This is the single file to read after a barge-in test.
    session_log_handler = attach_session_log(session_id)
    logger.info(f"[{session_id}] === CALL START === (log file: logs/sessions/{session_id}.log)")

    #create shared websocket lock to prevent concurrent writes to the same WebSocket
    ws_lock = asyncio.Lock()

    # Initialize variables to avoid NameError on early exit
    orchestrator = None
    pipeline_task = None
    audio_sender = None
    sender_task = None
    heartbeat_task = None

    async def heartbeat():
        try:
            while True:
                await asyncio.sleep(20)
                async with ws_lock:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                logger.debug(f"[{session_id}] Heartbeat ping sent.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{session_id}] Heartbeat error: {e}")

    try:
        #register connection with our central connection manager
        await connection_manager.connect(session_id, websocket)

        # Check if Silero VAD is active and healthy
        from backend.app.services.silero_service import is_silero_healthy
        if not is_silero_healthy():
            logger.error(f"[{session_id}] Rejecting connection: Silero VAD service is not active.")
            try:
                async with ws_lock:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "The VAD/pipeline service is currently unavailable. Please try again later."
                    }))
            except Exception:
                pass
            await websocket.close(code=1011)
            return

        #instantiate the audio receiver and sender for this session
        audio_receiver = AudioReceiver(session_id)

        # Create a shared interrupt event that both the Orchestrator and AudioSender will use.
        # This ensures the send_loop can drop in-flight chunks the moment a barge-in fires.
        interrupt_event = asyncio.Event()
        audio_sender = AudioSender(session_id, ws_lock, interrupt_event)

        #start the audio sender loop in the background concurrently with the main WebSocket loop
        sender_task = asyncio.create_task(audio_sender.send_loop())

        # we will orchestrate the entire STT -> LLM -> TTS pipeline in a separate task
        orchestrator = SessionOrchestrator(session_id, websocket, audio_receiver, audio_sender, ws_lock, interrupt_event)
        pipeline_task = asyncio.create_task(orchestrator.run())

        # Start keepalive heartbeat task
        heartbeat_task = asyncio.create_task(heartbeat())

        logger.info(f"[{session_id}] Full-duplex streaming connection established.")

        #the inbound continuous listening loop for receiving audio chunks from the client
        while True:  #loop indefinitely until the client disconnects or an error occurs
            try:
                #capture the raw binary pacets coming form the client mic
                data = await websocket.receive_bytes()
            except WebSocketDisconnect:
                raise
            except Exception as ws_err:
                logger.error(f"[{session_id}] Error receiving bytes from WebSocket: {ws_err}")
                raise

            if orchestrator and orchestrator.is_closing():
                continue

            try:
                #drop them in receiver's queue buffer
                await audio_receiver.enqueue_chunk(data)

                # process raw audio through VAD for barge-in detection
                await orchestrator.handle_raw_audio(data)
            except Exception as processing_err:
                logger.error(f"[{session_id}] Error processing inbound audio chunk: {processing_err}")

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"[{session_id}] Error in Websocket gateway: {e}")

    finally:
        # Stop keepalive heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

        # gracefully shutdown the orchestrator and clean up resources
        if orchestrator:
            await orchestrator.shutdown()

        if pipeline_task:
            pipeline_task.cancel()
            with contextlib.suppress(Exception):
                await pipeline_task
            
        if audio_sender:
            audio_sender.stop()
        if sender_task:
            sender_task.cancel()

        await connection_manager.disconnect(session_id)

        logger.info(f"[{session_id}] === CALL END ===")
        detach_session_log(session_log_handler)