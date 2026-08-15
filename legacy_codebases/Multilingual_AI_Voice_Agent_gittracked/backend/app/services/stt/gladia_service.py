from __future__ import annotations
import os
import asyncio
import contextlib
import logging
from gladiaio_sdk import GladiaClient
from dataclasses import dataclass
from collections.abc import Callable
from typing import Any
import importlib

from backend.app.transport.audio_receiver import AudioReceiver
from backend.app.core.config.config import get_settings
from backend.app.core.interfaces import Transcript, TranscriptCallback
settings = get_settings() #get validated settings from config.py

logger = logging.getLogger(__name__)


# STAGE 1: Define the configuration for the Gladia API.
# This function builds the precise settings we need for fast, bilingual transcription.
def _build_live_init_request() -> Any:
    """Build a Gladia live session request with low-latency voice-agent settings."""

    try:
        generated_types = importlib.import_module("gladiaio_sdk.v2.live.generated_types")
    except Exception as exc: 
        raise RuntimeError("The gladiaio-sdk package is required to use GladiaService.") from exc

    LiveV2InitRequest = getattr(generated_types, "LiveV2InitRequest")
    LiveV2LanguageConfig = getattr(generated_types, "LiveV2LanguageConfig")
    LiveV2MessagesConfig = getattr(generated_types, "LiveV2MessagesConfig")

    return LiveV2InitRequest(
        model="solaria-1",
        encoding="wav/pcm",
        sample_rate=16000,
        bit_depth=16,
        channels=1,
        endpointing=0.2,

        language_config=LiveV2LanguageConfig(
            languages=["ur", "en", "ar", "ms"],
            code_switching=True,
        ),

        messages_config=LiveV2MessagesConfig(
            receive_partial_transcripts=True,
            receive_final_transcripts=True,
            receive_speech_events=False,
            receive_pre_processing_events=False,
            receive_realtime_processing_events=False,
            receive_post_processing_events=False,
            receive_acknowledgments=False,
            receive_errors=True,
            receive_lifecycle_events=False,
        ),
    )


# STAGE 2: Define the clean data structure for our results.
# This dataclass ensures all transcripts are in a consistent format for the next phase (LLM).
@dataclass(slots=True)
class GladiaTranscript:
    """Normalized transcript payload passed to downstream consumers."""

    session_id: str
    text: str
    is_final: bool
    language: str | None = None
    raw_message: dict[str, Any] | None = None


# STAGE 3: Create a helper to parse incoming messages.
# This utility function unpacks the raw data from Gladia and finds the actual text.
def _extract_text(message: Any) -> tuple[str, bool, str | None, dict[str, Any] | None]:
    """Extract the transcript text and metadata from a Gladia websocket message."""

    raw_dict: dict[str, Any] | None = None
    if hasattr(message, "to_dict"):
        try:
            raw_dict = message.to_dict()
        except Exception:
            raw_dict = None
    elif isinstance(message, dict):
        raw_dict = message

    if raw_dict is None and hasattr(message, "__dict__"):
        raw_dict = {
            key: value
            for key, value in vars(message).items()
            if not key.startswith("_")
        }

    message_type = getattr(message, "type", None) or (raw_dict or {}).get("type")
    if message_type != "transcript":
        return "", False, None, raw_dict

    data = getattr(message, "data", None) or (raw_dict or {}).get("data") or {}
    utterance = getattr(data, "utterance", None) if not isinstance(data, dict) else data.get("utterance", {})
    utterance = utterance or {}

    text = getattr(utterance, "text", None) if not isinstance(utterance, dict) else utterance.get("text")
    text = text or (getattr(data, "text", None) if not isinstance(data, dict) else data.get("text")) or ""

    is_final = bool(getattr(data, "is_final", None) if not isinstance(data, dict) else data.get("is_final", False))
    language = getattr(data, "language", None) if not isinstance(data, dict) else data.get("language")
    language = language or (
        getattr(utterance, "language", None) if not isinstance(utterance, dict) else utterance.get("language")
    )
    return str(text).strip(), is_final, language, raw_dict


# STAGE 4: Build the main service class that orchestrates the entire STT pipeline.
class GladiaService:
    """Asynchronous Gladia Live V2 worker for Minglish transcription.

    The service deliberately decouples audio ingestion from transcript handling:
    - ``_send_audio_loop`` drains Phase 1 audio buffers and streams them to Gladia.
    - ``_receive_loop`` consumes queued transcript events and normalizes them for downstream LLM consumers."""

    # This sets up the initial state for a new user session.
    # It creates queues and flags to manage the concurrent tasks.
    def __init__(self, session_id: str, audio_receiver: AudioReceiver, api_key: str | None = None) -> None:
        self.session_id = session_id
        self.audio_receiver = audio_receiver
        self._running = asyncio.Event()
        self._ended_evt = asyncio.Event()
        self._api_key = api_key
        self._running.set() # initialising the loops to run, when stop .clear() is called
        self._stop_lock = asyncio.Lock()    # ensures only one process can stop the session at a time
        self._session: Any | None = None
        self._transcript_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=50)
        self._transcript_callbacks: list[TranscriptCallback] = []
        self._message_callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._audio_task: asyncio.Task[None] | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self.last_error: Exception | None = None

    # This is the main entry point to kick off the transcription process.
    # It connects to Gladia and starts the two main loops for sending and receiving data.
    async def start(self) -> None:
        """Create the Gladia live session and run both worker loops concurrently."""
        self._ended_evt.clear()
        try:
            session = await self._create_session()
            self._session = session
        except Exception as exc:
            self.last_error = exc
            logger.error("[%s] Gladia session initialization failed: %s", self.session_id, exc)
            return

        self._bind_session_events(session)
        logger.info("[%s] Gladia session started.", self.session_id)

        self._audio_task = asyncio.create_task(self._send_audio_loop(), name=f"gladia-audio-{self.session_id}")
        self._receive_task = asyncio.create_task(self._receive_loop(), name=f"gladia-recv-{self.session_id}")

        try:
            await asyncio.gather(self._audio_task, self._receive_task)
        finally:
            # Ensure we clean up the session and cancel any remaining tasks if the main loop exits.
            await self.stop_recording()

    async def stop(self) -> None:
        """Satisfies STTProvider interface. Aliases stop_recording."""
        await self.stop_recording()

    # This is the cleanup crew. It ensures we safely disconnect from Gladia
    # and stop all background tasks when the user's session ends.
    async def stop_recording(self) -> None:
        """Idempotently stop the Gladia live session and cancel all workers."""

        async with self._stop_lock:
            if not self._running.is_set() and self._session is None:
                return

            # 1. Signal workers to stop
            self._running.clear()

            # 2. Tell Gladia to stop the session
            if self._session is not None:
                try:
                    stop_recording = getattr(self._session, "stop_recording", None)
                    if callable(stop_recording):
                        result = stop_recording()
                        if asyncio.iscoroutine(result):
                            await result
                        
                        # Wait for the ended event from the websocket with a safe timeout
                        with contextlib.suppress(asyncio.TimeoutError):
                            await asyncio.wait_for(self._ended_evt.wait(), timeout=1.0) 
                except Exception:
                    logger.exception("[%s] Failed while stopping Gladia session.", self.session_id)
                
                self._session = None

            # 3. Cancel background tasks
            for task in (self._audio_task, self._receive_task):
                if task and not task.done():
                    task.cancel()

            # 4. Wait for tasks to finish
            for task in (self._audio_task, self._receive_task):
                if task is None:
                    continue
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            self._audio_task = None
            self._receive_task = None
            logger.info("[%s] Gladia session stopped and connection closed.", self.session_id)

    # These methods allow other parts of our app (like the future LLM service)
    # to listen for new transcripts without needing to know how Gladia works.
    def on_transcript(self, callback: TranscriptCallback) -> None:
        """Register a callback for normalized transcript events."""

        self._transcript_callbacks.append(callback)

    def on_message(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback for raw websocket payloads."""

        self._message_callbacks.append(callback)

    def _log_callback_task_result(self, task: asyncio.Task[Any]) -> None:
        """Surface background callback failures instead of letting asyncio discard them."""

        try:
            exc = task.exception()
        except asyncio.CancelledError:
            return

        if exc is not None:
            logger.error(
                "[%s] Async transcript callback failed.",
                self.session_id,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    # --- Internal Core Logic ---

    # This helper method handles the initial handshake with the Gladia API.
    # It uses the configuration from STAGE 1 to create the connection.
    async def _create_session(self) -> Any:
        """Create a live transcription session using the official SDK."""

        client = GladiaClient(api_key=self._api_key or settings.gladia_api_key)
        live_client = None

        for candidate_name in ("live_v2_async", "live_async"):
            candidate = getattr(client, candidate_name, None)
            if callable(candidate):
                live_client = candidate()
                break

        if live_client is None:
            raise RuntimeError("Unable to locate a Gladia live async client on GladiaClient.")

        init_request = _build_live_init_request()

        start_session = getattr(live_client, "start_session", None)
        if not callable(start_session):
            raise RuntimeError("Gladia live client does not expose start_session().")

        session = start_session(init_request)
        if asyncio.iscoroutine(session):
            session = await session

        return session

    # Once connected, this method hooks our code into the Gladia SDK's events.
    # It tells the SDK to put any new messages into our internal queue.
    def _bind_session_events(self, session: Any) -> None:
        """Bridge Gladia websocket events into the local transcript queue."""

        on_message = getattr(session, "on", None)
        if not callable(on_message):
            logger.warning("[%s] Gladia session does not expose event hooks; receive loop will be idle.", self.session_id)
            return

        @on_message("message")
        def _handle_message(message: Any) -> None:
            try:
                payload_text, is_final, language, raw_dict = _extract_text(message)
                if not payload_text:
                    return

                normalized = {
                    "session_id": self.session_id,
                    "text": payload_text,
                    "is_final": is_final,
                    "language": language,
                    "raw_message": raw_dict,
                }
                try:
                    self._transcript_queue.put_nowait(normalized)
                except asyncio.QueueFull:
                    logger.warning("[%s] Transcript queue full — dropping transcript.", self.session_id)
            except Exception:
                logger.exception("[%s] Failed to process Gladia websocket message.", self.session_id)

        @on_message("error")
        def _handle_error(error: Exception) -> None:
            logger.exception("[%s] Gladia session error: %s", self.session_id, error)
            self.last_error = error

        @on_message("ended")
        def _handle_ended(_: Any) -> None:
            self._running.clear()
            self._ended_evt.set()

    # THE FIRST WORKER: This loop's only job is to pull audio from the
    # receiver queue (Phase 1) and immediately send it to Gladia.
    async def _send_audio_loop(self) -> None:
        """Drain PCM audio from Phase 1 and stream it to Gladia."""

        logger.info("[%s] Gladia audio sender loop started.", self.session_id)
        try:
            while self._running.is_set():
                try:
                    chunk = await self.audio_receiver.get_next_chunk()
                    await self.publish_audio(chunk)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("[%s] Error while sending audio to Gladia.", self.session_id)
        except asyncio.CancelledError:
            logger.info("[%s] Gladia audio sender loop cancelled.", self.session_id)

    # THE SECOND WORKER: This loop listens for new transcripts from the internal queue,
    # cleans them up, and passes them to any downstream listeners (like the LLM).
    async def _receive_loop(self) -> None:
        """Consume transcript events from the Gladia websocket callback bridge."""

        logger.info("[%s] Gladia transcript receive loop started.", self.session_id)
        try:
            while self._running.is_set():
                try:
                    payload = await self._transcript_queue.get()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("[%s] Error waiting for transcript payload.", self.session_id)
                    continue

                try:
                    gladia_transcript = GladiaTranscript(
                        session_id=str(payload.get("session_id", self.session_id)),
                        text=str(payload.get("text", "")).strip(),
                        is_final=bool(payload.get("is_final", False)),
                        language=payload.get("language"),
                        raw_message=payload.get("raw_message"),
                    )

                    if not gladia_transcript.text:
                        continue

                    # Log the transcript for debugging and monitoring purposes seperatly for clean logging
                    if gladia_transcript.is_final:
                        logger.info("[%s] Final transcript: %s", self.session_id, gladia_transcript.text)
                    else:
                        logger.debug("[%s] Interim transcript: %s", self.session_id, gladia_transcript.text)

                    core_transcript = Transcript(
                        session_id=gladia_transcript.session_id,
                        text=gladia_transcript.text,
                        is_final=gladia_transcript.is_final,
                        language=gladia_transcript.language or "",
                    )

                    # feeding to phase 3 LLM callback, we can have multiple callbacks registered for different purposes
                    for callback in list(self._transcript_callbacks):
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                # fire and forget async Groq LLM task so the loop keep reading
                                task = asyncio.create_task(callback(core_transcript))
                                task.add_done_callback(self._log_callback_task_result)
                            else:
                                callback(core_transcript)
                        except Exception:
                            logger.exception("[%s] Transcript callback failed.", self.session_id)

                    for callback in list(self._message_callbacks):
                        try:
                            callback(payload)
                        except Exception:
                            logger.exception("[%s] Raw message callback failed.", self.session_id)
                finally:
                    self._transcript_queue.task_done()
        except asyncio.CancelledError:
            logger.info("[%s] Gladia transcript receive loop cancelled.", self.session_id)

    # This is a low-level helper that directly sends a chunk of audio
    # over the WebSocket to Gladia. It's called by the _send_audio_loop.
    async def publish_audio(self, chunk: bytes) -> None:
        """Push raw audio into the underlying Gladia session immediately."""

        session = self._session
        if session is None:
            return

        try:
            send_audio = getattr(session, "send_audio", None)
            if callable(send_audio):
                result = send_audio(chunk)
                if asyncio.iscoroutine(result):
                    await result
        except Exception:
            logger.exception("[%s] Failed to send audio chunk to Gladia.", self.session_id)
