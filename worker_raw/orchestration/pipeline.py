"""UCVE Real-Time Pipeline Orchestrator."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import NAMESPACE_DNS, UUID, uuid5

from core.buffers.cancellation import AsyncioCancellationToken
from core.buffers.policy import OUTBOUND_TTS_POLICY
from core.buffers.typed_queue import TypedAsyncQueue
from core.compliance.audit.writer import AuditWriter
from core.compliance.redaction import RedactionService
from core.compliance.redaction_policy import RedactionPolicy
from core.compliance.tenant_profile import (
    TenantComplianceProfileLoader,
    assert_cloud_llm_allowed,
)
from core.errors.codes import UCVEError, UCVEErrorCode
from core.errors.parse_uuid import parse_uuid
from core.fsm.barge_in import BargeInController
from core.fsm.cancel_contract import ThreePointCancel
from core.fsm.events import SessionEvent
from core.fsm.session_fsm import SessionFSM
from core.fsm.states import SessionState
from core.language.chunker import SentenceChunker
from core.language.normalizer import TextNormalizer
from core.language.router import LanguageRouter
from core.listening.barge_verify import BargeVerifyEngine
from core.listening.config import FRAME_MS, ListeningPipelineConfig, SpeakingPipelineConfig
from core.listening.speech_capture import SpeechCaptureEngine
from core.listening.vad_worker import VADWorker
from core.mcp.filler import ConversationalFillerSynth, FillerConfig
from core.providers.adapters.gladia_live_stt import GladiaLiveSTTSession
from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from core.metering.usage_meter import UsageMeter
from core.observability.logging import get_logger
from core.providers.adapters.cartesia_tts import CartesiaTTSProvider
from core.providers.adapters.deepgram_stt import DeepgramSTTProvider
from core.providers.adapters.elevenlabs_tts import ElevenLabsTTSProvider
from core.providers.adapters.gemini_llm import GeminiLLMProvider
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.null_llm import NullLLMProvider
from core.providers.adapters.null_stt import NullSTTProvider
from core.providers.adapters.null_tts import NullTTSProvider
from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.factory import (
    build_llm_provider,
    build_stt_provider,
    build_tts_provider,
    normalize_llm_provider,
    normalize_stt_provider,
    normalize_tts_provider,
)
from core.providers.failover import FailoverRouter
from core.providers.interfaces.llm import LLMConfig
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.providers.registry import ProviderRegistry
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval
from core.session.redis_store import RedisSessionStore
from core.transport.resample_egress import EgressResampler
from core.types.audio import AudioFrame
from core.types.events import ControlEventType
from core.vad.silero_adapter import SileroVADAdapter
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.pipeline.enqueue import PostCallPipeline
from worker_raw.orchestration.latency_hooks import LatencyHooks
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.orchestration.tool_handler import PipelineToolHandler

logger = get_logger("ucve.orchestrator")


def _metric_session_uuid(session_id: str) -> UUID:
    """Correlation UUID for latency waterfall (deterministic for non-UUID test ids)."""
    try:
        return UUID(session_id)
    except ValueError:
        return uuid5(NAMESPACE_DNS, f"ucve-session:{session_id}")

ProviderRegistry.register_provider_class("gladia", GladiaSTTProvider)
ProviderRegistry.register_provider_class("deepgram", DeepgramSTTProvider)
ProviderRegistry.register_provider_class("groq", GroqLLMProvider)
ProviderRegistry.register_provider_class("gemini", GeminiLLMProvider)
ProviderRegistry.register_provider_class("openai", OpenAILLMProvider)
ProviderRegistry.register_provider_class("uplift", UpliftTTSProvider)
ProviderRegistry.register_provider_class("elevenlabs", ElevenLabsTTSProvider)
ProviderRegistry.register_provider_class("cartesia", CartesiaTTSProvider)


class PipelineOrchestrator:
    """Orchestrates end-to-end real-time talking session pipeline."""

    def __init__(
        self,
        *,
        allow_testing_providers: bool = True,
        on_audio_out: Callable[[bytes], Any] | None = None,
        on_transcript: Callable[[str, str], Any] | None = None,
        tool_handler: PipelineToolHandler | None = None,
        latency_collector: LatencyCollector | None = None,
        rag_retriever: PgVectorRetriever | None = None,
        post_call_pipeline: PostCallPipeline | None = None,
    ) -> None:
        self.allow_testing_providers = allow_testing_providers
        self.on_audio_out = on_audio_out
        self.on_transcript = on_transcript
        self.tool_handler = tool_handler or PipelineToolHandler()
        self.latency_collector = latency_collector or LatencyCollector()
        self.latency_hooks = LatencyHooks(self.latency_collector)
        self.rag_retriever = rag_retriever or PgVectorRetriever()
        self.speculative_rag = SpeculativeRetrieval(self.rag_retriever)
        self.post_call_pipeline = post_call_pipeline or PostCallPipeline()
        self.listening_config = ListeningPipelineConfig.from_env()
        self.speaking_config = SpeakingPipelineConfig.from_env()
        self.vad_adapter = SileroVADAdapter()
        self._apply_vad_timing()
        self.stt_provider = GladiaSTTProvider(mock_text=self.listening_config.stt_mock_text)
        self.llm_provider = GroqLLMProvider()
        self.tts_provider = UpliftTTSProvider(
            chunk_size_bytes=(
                self.speaking_config.tts_chunk_size_bytes
                if self.speaking_config.enable_speaking_hardening
                else 3200
            )
        )
        self._active_stt_id = "gladia"
        self._active_llm_id = "groq"
        self._active_tts_id = "uplift"
        self.failover_router = FailoverRouter(priority=["primary", "secondary"])
        self.language_router = LanguageRouter()
        self.normalizer = TextNormalizer()
        self.chunker = SentenceChunker()
        self.redis_store = RedisSessionStore()
        self.barge_in_controller = BargeInController()
        self.three_point_cancel = ThreePointCancel()
        self.audit_writer = AuditWriter()
        self.usage_meter = UsageMeter()
        self.redaction_service = RedactionService()
        self.fsm = SessionFSM()
        self._tts_task: asyncio.Task[None] | None = None
        self._llm_task: asyncio.Task[None] | None = None
        self._started_at = time.monotonic()
        self._session_start_monotonic = time.monotonic()
        self._turn_starts: list[float] = []
        self._turn_ends: list[float] = []
        self._ws_session: Any | None = None
        self._egress_queue: TypedAsyncQueue[bytes] = TypedAsyncQueue(OUTBOUND_TTS_POLICY)
        self._egress_sender_task: asyncio.Task[None] | None = None
        self._llm_cancel = AsyncioCancellationToken()
        self._tts_cancel = AsyncioCancellationToken()
        self._playback_started = False
        self._finalized_once = False
        self._speech_buffer = bytearray()
        self._capturing_speech = False
        self._speech_end_pending = False
        self._last_acoustic_speech_ms: float = 0.0
        self._last_vad_speech_end_ms: float = 0.0
        self._last_stt_final_ms: float = 0.0

        # --- V2 listening/speaking pipeline (feature-flagged) ----------------
        lc = self.listening_config
        self._speech_capture: SpeechCaptureEngine | None = (
            SpeechCaptureEngine(self.vad_adapter, lc) if lc.use_speech_capture else None
        )
        self._barge_verify: BargeVerifyEngine | None = (
            BargeVerifyEngine(lc, speech_threshold=lc.vad_threshold)
            if lc.enable_barge_verify
            else None
        )
        self._vad_worker: VADWorker | None = (
            VADWorker() if lc.enable_vad_worker else None
        )
        self._live_stt: GladiaLiveSTTSession | None = None
        self._live_stt_task: asyncio.Task[None] | None = None
        self._live_final_text: str = ""
        self._filler: ConversationalFillerSynth | None = None
        # Playback pause gate for barge verification (set => audio flows).
        self._playback_pause_event = asyncio.Event()
        self._playback_pause_event.set()
        self._barge_verify_task: asyncio.Task[None] | None = None
        self._active_latency_turn_id: UUID | None = None
        # Always flush egress on three-point cancel (fixes ghost audio after barge).
        self.three_point_cancel.register_flush_callback(self._flush_egress_queue)

    async def apply_provider_selection(self, session_config: PipelineSessionConfig) -> None:
        """Swap STT/LLM/TTS adapters from session config (call at session start only)."""
        stt_id = normalize_stt_provider(session_config.stt_provider)
        llm_id = normalize_llm_provider(session_config.llm_provider)
        tts_id = normalize_tts_provider(session_config.tts_provider)
        session_config.stt_provider = stt_id
        session_config.llm_provider = llm_id
        session_config.tts_provider = tts_id

        if stt_id != self._active_stt_id:
            self.stt_provider = build_stt_provider(
                stt_id, mock_text=self.listening_config.stt_mock_text
            )
            self._active_stt_id = stt_id

        llm_model_choice = getattr(session_config, "llm_model", None)
        if llm_id != self._active_llm_id or getattr(self, "_active_llm_model", None) != llm_model_choice:
            old = self.llm_provider
            self.llm_provider = build_llm_provider(llm_id, model=llm_model_choice)
            self._active_llm_id = llm_id
            self._active_llm_model = llm_model_choice
            close_fn = getattr(old, "aclose", None)
            if close_fn:
                maybe = close_fn()
                if asyncio.iscoroutine(maybe):
                    await maybe

        if tts_id != self._active_tts_id:
            old_tts = self.tts_provider
            self.tts_provider = build_tts_provider(
                tts_id, speaking_config=self.speaking_config
            )
            self._active_tts_id = tts_id
            close_fn = getattr(old_tts, "aclose", None)
            if close_fn:
                maybe = close_fn()
                if asyncio.iscoroutine(maybe):
                    await maybe

        logger.info(
            "Session providers active",
            stt=stt_id,
            llm=llm_id,
            tts=tts_id,
        )

    def _apply_vad_timing(self) -> None:
        """Apply VAD hysteresis timing per active feature flags."""
        lc = self.listening_config
        if lc.enable_vad_timing:
            self.vad_adapter.configure(
                min_speech_frames=lc.vad_min_speech_frames,
                min_silence_frames=lc.vad_min_silence_frames,
                threshold=lc.vad_threshold,
            )
        elif lc.enable_quick_wins:
            # Phase 0 quick win: longer endpoint + onset debounce, no full retune.
            self.vad_adapter.configure(min_speech_frames=4, min_silence_frames=12)

    def _flush_egress_queue(self) -> None:
        """Drop any queued-but-unsent agent audio (three-point cancel: sender)."""
        dropped = 0
        while not self._egress_queue.empty():
            try:
                self._egress_queue.get_nowait()
                dropped += 1
            except Exception:
                break
        if dropped > 0:
            logger.info("Flushed egress audio queue on barge-in", dropped_chunks=dropped)

    def attach_ws_session(self, session: Any) -> None:
        self._ws_session = session
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    def apply_language_vad_overrides(self, language: str) -> None:
        """Wire per-language VAD silence overrides from the language profile registry."""
        try:
            from core.language.registry import LanguageRegistry

            profile = LanguageRegistry.load_defaults().get_profile(language)
            if profile is None:
                return
            override_ms = int(getattr(profile, "vad_silence_override_ms", 0) or 0)
            if override_ms > 0 and self.listening_config.enable_vad_timing:
                frames = max(1, round(override_ms / FRAME_MS))
                self.vad_adapter.configure(min_silence_frames=frames)
        except Exception as exc:
            logger.debug("Language VAD override skipped", error=str(exc))

    async def _egress_sender_loop(self) -> None:
        while True:
            try:
                pcm = await self._egress_queue.get()
            except asyncio.CancelledError:
                break
            # Block while playback is paused during a barge verification window.
            if not self._playback_pause_event.is_set():
                try:
                    await self._playback_pause_event.wait()
                except asyncio.CancelledError:
                    break
            if self.on_audio_out:
                maybe = self.on_audio_out(pcm)
                if asyncio.iscoroutine(maybe):
                    await maybe

    def pause_playback(self) -> None:
        """Pause egress to the client (barge verify window)."""
        self._playback_pause_event.clear()

    def resume_playback(self) -> None:
        """Resume egress to the client after a false-alarm barge."""
        self._playback_pause_event.set()

    async def _ensure_egress_sender(self) -> None:
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    async def _emit_audio(self, pcm: bytes, waterfall: Any | None = None) -> None:
        if not self._playback_started:
            self._playback_started = True
            if waterfall is not None:
                waterfall.server_send_ms = self.latency_hooks.now_ms()
                session = self._ws_session
                transport = (
                    getattr(session, "transport", None) if session is not None else None
                )
                if transport is not None:
                    try:
                        await transport.send_control_event(
                            "audio_start",
                            {
                                "turn_id": str(waterfall.turn_id),
                                "server_send_ms": waterfall.server_send_ms,
                                "clock_domain": waterfall.clock_domain,
                            },
                        )
                    except Exception as exc:
                        logger.debug("Client audio_start notify failed", error=str(exc))
            if self.fsm.can_transition(SessionEvent.TTS_FIRST_BYTE):
                self.fsm.trigger(SessionEvent.TTS_FIRST_BYTE)
        await self._ensure_egress_sender()
        await self._egress_queue.put(pcm)

    async def _notify_client_barge_in(self, reason: str = "barge_in_committed") -> None:
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await transport.send_control_event(
                ControlEventType.BARGE_IN, {"reason": reason}
            )
        except Exception as exc:
            logger.debug("Client barge_in notify failed", error=str(exc))

    async def _emit_latency_telemetry(self, waterfall: LatencyWaterfall) -> None:
        """Broadcast the canonical versioned latency payload to the client."""
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            payload = waterfall.to_metric_payload()
            payload["population"] = self.latency_collector.percentile_summary()
            await transport.send_control_event(ControlEventType.METRIC, payload)
        except Exception as exc:
            logger.debug("Failed to emit latency telemetry", error=str(exc))

    async def _emit_debug_listening(self, evt: Any, frame: AudioFrame) -> None:
        if not self.listening_config.debug_listening:
            return
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        rms = 0.0
        gated = False
        if self._speech_capture is not None:
            rms = self._speech_capture.last_rms
            gated = self._speech_capture.last_gated
        try:
            await transport.send_control_event(
                ControlEventType.METRIC,
                {
                    "kind": "vad_debug",
                    "prob": getattr(evt, "probability", 0.0),
                    "speech_start": bool(getattr(evt, "speech_start", False)),
                    "speech_end": bool(getattr(evt, "speech_end", False)),
                    "rms": rms,
                    "gated": gated,
                    "bytes": len(frame.pcm16 or b""),
                },
            )
        except Exception:
            pass

    async def _run_barge_verify(self) -> None:
        """Pause → verify → commit or resume (Phase 4)."""
        engine = self._barge_verify
        if engine is None:
            return

        async def _pause() -> None:
            self.pause_playback()

        async def _resume() -> None:
            self.barge_in_controller._false_alarm(reason="Barge verify false alarm")
            self.resume_playback()

        async def _commit() -> None:
            self.barge_in_controller._commit_barge_in(
                reason="Barge verify sustained speech"
            )
            # Unblock egress gate for the *next* turn (queue already flushed).
            self.resume_playback()
            await self._notify_client_barge_in()
            if self._speech_capture is not None:
                self._speech_capture.begin_capture()
                self._capturing_speech = True
            else:
                self._capturing_speech = True
            await self._maybe_start_live_stt()

        await engine.run(
            pause=_pause,
            resume=_resume,
            commit=_commit,
            is_speaking=lambda: bool(self.vad_adapter.is_speaking),
        )

    async def execute_immediate_barge_in(self, reason: str = "VAD speech onset") -> None:
        """Instant sub-100ms barge-in: cancel LLM/TTS, flush queues, notify client, transition FSM."""
        logger.info("Executing immediate barge-in", reason=reason, state=str(self.fsm.state))
        if self._active_latency_turn_id is not None:
            self.latency_collector.cancel_turn(
                self._active_latency_turn_id,
                reason="barge_in",
            )
        if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
            self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
        self._llm_cancel.cancel()
        self._tts_cancel.cancel()
        self.three_point_cancel.execute_cancel_and_flush()
        self._flush_egress_queue()
        self.resume_playback()
        await self._notify_client_barge_in(reason=reason)
        self.barge_in_controller._commit_barge_in(reason=reason)
        self._capturing_speech = True
        await self._maybe_start_live_stt()

    async def _maybe_start_live_stt(self) -> None:
        if not self.listening_config.enable_streaming_stt:
            return
        if self._live_stt is not None and self._live_stt.is_live:
            return
        cfg = getattr(self._ws_session, "config", None) if self._ws_session else None
        language = getattr(cfg, "language", "en") if cfg else "en"
        session = GladiaLiveSTTSession(
            language=language,
            endpointing=self.listening_config.gladia_endpointing,
            receive_partials=self.listening_config.gladia_receive_partials,
        )
        started = await session.start()
        self._live_stt = session
        if started:
            self._live_stt_task = asyncio.create_task(self._consume_live_stt())

    async def _consume_live_stt(self) -> None:
        session = self._live_stt
        if session is None:
            return
        try:
            async for transcript in session.transcripts():
                text = (transcript.text or "").strip()
                if not text:
                    continue
                if not transcript.is_final:
                    self.barge_in_controller.buffer_partial(text)
                    if self._barge_verify is not None:
                        self._barge_verify.note_partial(text)
                    await self._maybe_speculate_rag(text)
                else:
                    self._last_stt_final_ms = time.monotonic() * 1000.0
                    self.barge_in_controller.buffer_final(text)
                    self._live_final_text = text
                    # Drive the turn immediately — do not wait for the next mic
                    # frame (silence/mute previously left finals stranded).
                    runner = self._ws_session
                    enqueue = getattr(runner, "enqueue_voice_turn", None) if runner else None
                    if enqueue is not None:
                        await enqueue(text)
                        self._live_final_text = ""
                        self._speech_end_pending = False
                        self._speech_buffer = bytearray()
                        self._capturing_speech = False
                        if self._speech_capture is not None:
                            self._speech_capture.reset()
                    else:
                        self._speech_end_pending = True
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.warning("Live STT consumer ended", error=str(exc))
            # Mark session dead so the next speech_start reconnects.
            live = self._live_stt
            if live is not None:
                live._live = False  # type: ignore[attr-defined]

    async def _maybe_speculate_rag(self, partial: str) -> None:
        if not self.listening_config.enable_rag_speculative:
            return
        cfg = getattr(self._ws_session, "config", None) if self._ws_session else None
        if cfg is None:
            return
        try:
            tenant_uuid = parse_uuid(cfg.tenant_id, "tenant_id")
        except Exception:
            return
        try:
            await self.speculative_rag.speculate(partial, tenant_uuid)
        except Exception as exc:
            logger.debug("RAG speculate skipped", error=str(exc))

    async def _close_live_stt(self) -> None:
        task = self._live_stt_task
        self._live_stt_task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        live = self._live_stt
        self._live_stt = None
        if live is not None:
            try:
                await live.close()
            except Exception:
                pass

    async def _observe_frame(self, frame: AudioFrame, *, agent_speaking: bool) -> Any:
        """Run gate/VAD/capture off the event loop (optionally via VADWorker)."""
        if self._speech_capture is not None:
            fn = self._speech_capture.observe
            if self._vad_worker is not None:
                return await self._vad_worker.submit(fn, frame, agent_speaking)
            return await asyncio.to_thread(fn, frame, agent_speaking)
        if self._vad_worker is not None:
            return await self._vad_worker.submit(self.vad_adapter.process_frame, frame)
        return await asyncio.to_thread(self.vad_adapter.process_frame, frame)

    async def process_frame_async(self, frame: AudioFrame) -> Any:
        """Run VAD / speech-capture; drive barge-verify and live STT when flagged."""
        agent_speaking = self.fsm.state in (
            SessionState.AGENT_SPEAKING,
            SessionState.PROCESSING_INFERENCE,
            SessionState.BARGE_IN_VERIFY,
        )
        evt = await self._observe_frame(frame, agent_speaking=agent_speaking)

        if self._barge_verify is not None and self._barge_verify.is_verifying:
            self._barge_verify.note_vad(evt.probability)

        if evt.speech_start and self.fsm.state in (SessionState.AGENT_SPEAKING, SessionState.PROCESSING_INFERENCE):
            if self._barge_verify is not None:
                if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                    self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
                if not self._barge_verify.is_verifying and (
                    self._barge_verify_task is None or self._barge_verify_task.done()
                ):
                    self._barge_verify_task = asyncio.create_task(self._run_barge_verify())
                await self._emit_debug_listening(evt, frame)
                return evt
            await self.execute_immediate_barge_in(reason="VAD speech during agent TTS")
            await self._emit_debug_listening(evt, frame)
            return evt

        if evt.speech_start and not agent_speaking:
            if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
            if self._speech_capture is None:
                # Phase 0 quick win: do not clear buffer on onset (preserves lookback).
                if not self._capturing_speech and not self.listening_config.enable_quick_wins:
                    self._speech_buffer = bytearray()
                self._capturing_speech = True
            else:
                self._capturing_speech = self._speech_capture.capturing
            await self._maybe_start_live_stt()

        capturing = self._capturing_speech or (
            self._speech_capture is not None and self._speech_capture.capturing
        ) or self.fsm.state in (
            SessionState.USER_SPEAKING,
            SessionState.BARGE_IN_INTERRUPTED,
        )

        if capturing and evt.probability > 0.5:
            self._last_acoustic_speech_ms = self.latency_hooks.now_ms()

        # Always stream mic audio into the live Gladia session while it is up.
        # Legacy agents keep one live socket for the whole call; gating only on
        # "capturing" dropped frames around VAD edges and starved STT.
        if frame.pcm16 and self._live_stt is not None and self._live_stt.is_live:
            if capturing or not agent_speaking:
                await self._live_stt.send_audio(frame.pcm16)

        if capturing and frame.pcm16:
            if self._speech_capture is None:
                max_buf = 512 * 1024
                if len(self._speech_buffer) + len(frame.pcm16) <= max_buf:
                    self._speech_buffer.extend(frame.pcm16)

        if evt.speech_end:
            self._last_vad_speech_end_ms = time.monotonic() * 1000.0
            if self.fsm.state in (
                SessionState.USER_SPEAKING,
                SessionState.BARGE_IN_INTERRUPTED,
            ):
                if self.fsm.can_transition(SessionEvent.VAD_SPEECH_END):
                    self.fsm.trigger(SessionEvent.VAD_SPEECH_END)
            if self._speech_capture is not None:
                pcm = self._speech_capture.take_utterance()
                if pcm:
                    self._speech_buffer = bytearray(pcm)
                self._capturing_speech = False
            elif self._capturing_speech:
                self._capturing_speech = False
            # Do NOT call Gladia finish()/stop_recording here — that tears down
            # the live socket. Gladia endpointing emits finals via
            # enqueue_voice_turn. Batch STT only when live is unavailable.
            if not (self._live_stt is not None and self._live_stt.is_live):
                if not self._live_final_text:
                    self._speech_end_pending = True

        await self._emit_debug_listening(evt, frame)
        return evt

    async def transcribe_speech_buffer(self, session_config: PipelineSessionConfig) -> str:
        """Run STT on buffered mic audio after VAD speech_end (live final preferred)."""
        if self._live_final_text:
            text = self._live_final_text.strip()
            self._live_final_text = ""
            self._speech_buffer = bytearray()
            # Keep the live Gladia socket open across turns.
            return text

        if not self._speech_buffer:
            logger.info("STT skipped — empty speech buffer after VAD end")
            return ""

        pcm = bytes(self._speech_buffer)
        self._speech_buffer = bytearray()
        logger.info("Batch Gladia STT fallback", pcm_bytes=len(pcm))

        async def _audio_iter() -> AsyncIterator[AudioFrame]:
            yield AudioFrame(
                pcm16=pcm,
                sample_rate=16000,
                channel_count=1,
            )

        cfg = STTConfig(language=session_config.language)
        text = ""
        async for transcript in self.stt_provider.transcribe_stream(_audio_iter(), cfg):
            if transcript.text:
                text = transcript.text
        if text:
            self._last_stt_final_ms = self.latency_hooks.now_ms()
        return text.strip()

    def resume_listening(self) -> None:
        """Return FSM to LISTENING after empty/failed mic capture."""
        if self.fsm.state in (
            SessionState.PROCESSING_INFERENCE,
            SessionState.USER_SPEAKING,
        ):
            self.fsm._state = SessionState.LISTENING
        self._capturing_speech = False
        self._speech_end_pending = False
        self._live_final_text = ""
        if self._speech_capture is not None:
            self._speech_capture.reset()
        else:
            self.vad_adapter.reset()

    def process_frame(self, frame: AudioFrame) -> Any:
        if self._speech_capture is not None:
            agent_speaking = self.fsm.state in (
                SessionState.AGENT_SPEAKING,
                SessionState.BARGE_IN_VERIFY,
            )
            return self._speech_capture.observe(frame, agent_speaking=agent_speaking)
        return self.vad_adapter.process_frame(frame)

    async def cancel_tts(self) -> None:
        self._tts_cancel.cancel()
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass
        if self.fsm.can_transition(SessionEvent.TTS_DRAINED):
            self.fsm.trigger(SessionEvent.TTS_DRAINED)

    async def _synthesize_streaming(
        self, sentences: list[str], session_config: PipelineSessionConfig, waterfall: Any
    ) -> None:
        voice = session_config.tts_voice_id or "default"
        ttfb_recorded = False
        for sentence in sentences:
            if self._tts_cancel.is_cancelled or self.three_point_cancel.cancelled:
                break
            cfg = TTSConfig(voice_id=voice, sample_rate=16000)

            async def _invoke(_pid: str) -> bool:
                async for chunk in self.tts_provider.synthesize_stream(
                    sentence, cfg, cancellation_token=self._tts_cancel
                ):
                    if self._tts_cancel.is_cancelled:
                        break
                    if chunk.pcm_data:
                        nonlocal ttfb_recorded
                        if not ttfb_recorded:
                            waterfall.tts_ttfb_ms = self.latency_hooks.now_ms()
                            ttfb_recorded = True
                        pcm = chunk.pcm_data
                        native = int(getattr(chunk, "native_sample_rate", 16000) or 16000)
                        if native != 16000:
                            pcm = EgressResampler.resample_to_16k(pcm, native)
                        # Amplitude probe: separates silent vendor PCM from client playback bugs.
                        if getattr(self, "_tts_pcm_logged", 0) < 3 and len(pcm) >= 4:
                            import struct

                            n = min(64, len(pcm) // 2)
                            samples = struct.unpack("<" + "h" * n, pcm[: n * 2])
                            peak = max(abs(s) for s in samples) if samples else 0
                            logger.info(
                                "TTS PCM egress chunk",
                                bytes=len(pcm),
                                native_hz=native,
                                peak_abs=peak,
                            )
                            self._tts_pcm_logged = getattr(self, "_tts_pcm_logged", 0) + 1
                        await self._emit_audio(pcm, waterfall)
                return True

            try:
                await self.failover_router.call_with_failover(
                    "tts", session_config.language, _invoke, first_chunk_timeout=15.0
                )
            except Exception:
                null = NullTTSProvider()
                async for chunk in null.synthesize_stream(sentence, cfg):
                    if chunk.pcm_data:
                        await self._emit_audio(chunk.pcm_data, waterfall)

    async def run_turn(self, session_config: PipelineSessionConfig, user_text: str) -> str:
        """Execute one STT→RAG→LLM/Tool→norm→TTS turn with latency tracing."""
        turn_start = time.monotonic()
        self._turn_starts.append(turn_start)
        self._playback_started = False
        self._tts_pcm_logged = 0
        self._tts_cancel = AsyncioCancellationToken()
        self._llm_cancel = AsyncioCancellationToken()
        self.three_point_cancel.reset()
        self.three_point_cancel.register_flush_callback(self._flush_egress_queue)

        interrupted = self.barge_in_controller.next_turn_input()
        if interrupted:
            user_text = interrupted

        if session_config.compliance_tier in ("hipaa", "gdpr_strict"):
            redacted = self.redaction_service.redact_transcript(
                [{"speaker": "user", "text": user_text}],
                RedactionPolicy(redact_pii_in_transcript=True),
            )
            if redacted:
                user_text = str(redacted[0].get("text") or user_text)

        waterfall = self.latency_hooks.start_turn(
            _metric_session_uuid(session_config.session_id),
            acoustic_end_ms=self._last_acoustic_speech_ms or None,
            vad_end_ms=self._last_vad_speech_end_ms or None,
        )
        self._active_latency_turn_id = waterfall.turn_id
        self._last_acoustic_speech_ms = 0.0
        self._last_vad_speech_end_ms = 0.0
        if self._last_stt_final_ms > 0:
            waterfall.stt_final_ms = self._last_stt_final_ms
            self._last_stt_final_ms = 0.0
        sc = self.speaking_config
        self.apply_language_vad_overrides(session_config.language)

        try:
            policy = TenantComplianceProfileLoader.load_effective_policy(
                session_config.compliance_tier,
                hipaa_baa_acknowledged_at=(
                    time.time() if session_config.hipaa_baa_acknowledged else None
                ),
            )
            assert_cloud_llm_allowed(policy)
        except PermissionError as exc:
            raise UCVEError(
                UCVEErrorCode.HIPAA_BAA_REQUIRED,
                str(exc),
            ) from exc

        normalized = ""
        if self.on_transcript:
            maybe = self.on_transcript("user", user_text)
            if asyncio.iscoroutine(maybe):
                await maybe

        prior_turns = await self.redis_store.get_turns(session_config.session_id)
        await self.redis_store.append_turn(
            session_config.session_id,
            {"speaker": "user", "text": user_text, "language": session_config.language},
        )
        if self.fsm.state == SessionState.CONNECTING:
            self.fsm.trigger(SessionEvent.SESSION_ADMITTED)
        elif self.fsm.state == SessionState.AGENT_SPEAKING:
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        elif self.fsm.state == SessionState.BARGE_IN_INTERRUPTED:
            # Interrupted turn already in PROCESSING via VAD_SPEECH_END or stays until STT_FINAL.
            pass

        if self.fsm.state == SessionState.LISTENING:
            self.fsm.trigger(SessionEvent.STT_FINAL)
        elif self.fsm.state == SessionState.BARGE_IN_INTERRUPTED:
            if self.fsm.can_transition(SessionEvent.STT_FINAL):
                self.fsm.trigger(SessionEvent.STT_FINAL)

        rag_context = ""
        try:
            tenant_uuid = parse_uuid(session_config.tenant_id, "tenant_id")
        except UCVEError:
            if len(session_config.tenant_id) >= 35:
                raise
            tenant_uuid = None
        if tenant_uuid is not None:
            try:
                rag_chunks = await self.speculative_rag.reconcile(user_text, tenant_uuid)
                waterfall.rag_retrieve_ms = self.latency_hooks.now_ms()
                if rag_chunks:
                    rag_context = "\n".join(
                        f"[Knowledge DATA]: {c.text}" for c in rag_chunks
                    )
            except Exception as exc:
                logger.warning("RAG retrieval skipped", error=str(exc))

        prompt_str = (
            getattr(session_config, "system_prompt", None) or ""
        ).strip() or "You are a helpful voice agent."
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": f"{prompt_str}\n{rag_context}".strip()},
        ]
        # Multi-turn Redis history (Phase 7) — last 12 speaker turns.
        for turn in prior_turns[-12:]:
            speaker = (turn.get("speaker") or "user").lower()
            role = "assistant" if speaker in ("agent", "assistant") else "user"
            content = (turn.get("text") or "").strip()
            if content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_text})

        async def _run_tool_with_filler(tool_name: str, arguments: dict[str, Any]) -> str:
            filler_phrase: list[str] = []

            def _on_filler(phrase: str) -> None:
                filler_phrase.append(phrase)

            if sc.enable_tool_loop:
                self._filler = ConversationalFillerSynth(
                    FillerConfig(trigger_after_ms=sc.tool_filler_delay_ms),
                    on_filler_triggered=_on_filler,
                )
                await self._filler.start()
            try:
                if self.fsm.can_transition(SessionEvent.TOOL_CALL_START):
                    self.fsm.trigger(SessionEvent.TOOL_CALL_START)
                tool_res = await self.tool_handler.handle_tool_call(tool_name, arguments)
                if self.fsm.can_transition(SessionEvent.TOOL_RESULT):
                    self.fsm.trigger(SessionEvent.TOOL_RESULT)
            finally:
                if self._filler is not None:
                    self._filler.cancel()
                    self._filler = None
            if filler_phrase:
                await self._finish_turn_tts(filler_phrase[:1], session_config, waterfall)
            return str(tool_res.get("content", "Tool executed."))

        if user_text.startswith("tool:"):
            tool_name = user_text.split(":", 1)[1].strip()
            normalized = await _run_tool_with_filler(tool_name, {})
            await self._finish_turn_tts([normalized], session_config, waterfall)
        else:
            default_m = "gemini-2.5-flash" if self._active_llm_id == "gemini" else "openai/gpt-oss-120b"
            model = getattr(session_config, "llm_model", None) or getattr(self, "_active_llm_model", None) or default_m
            llm_cfg = LLMConfig(model=model)
            reply_parts: list[str] = []
            ttft_recorded = False
            chunker_recorded = False
            stream_buffer = ""
            pending_tool_calls: list[dict[str, Any]] = []
            # Queue-based TTS: stream sentence-level audio continuously
            tts_q: asyncio.Queue[str | None] = asyncio.Queue()
            spoken_chars = 0
            first_phrase_emitted = False

            async def _consume_tts_queue() -> None:
                while True:
                    item = await tts_q.get()
                    if item is None:
                        return
                    await self._synthesize_streaming(
                        [item], session_config, waterfall
                    )

            def _clean_speech_piece(p: str) -> str:
                # Strip orphan leading/trailing punctuation scraps like ", ", "- ", "; ", "— "
                return re.sub(r"^[\s,;:—\-\.\!\?]+|[\s,;:—\-]+$", "", p).strip()

            def _enqueue_stable_speech(*, final: bool = False) -> None:
                nonlocal spoken_chars, chunker_recorded, stream_buffer, first_phrase_emitted
                pending = stream_buffer[spoken_chars:]
                if not pending.strip():
                    return
                pieces: list[str] = []

                if final:
                    tail = _clean_speech_piece(pending)
                    if tail:
                        pieces.append(tail)
                else:
                    # Look for complete sentences first (. ! ?)
                    while True:
                        sent_match = re.search(r"^(.*?[\.\!\?]+)(?:\s+|$)", pending, flags=re.S)
                        if sent_match:
                            candidate = sent_match.group(1)
                            clean = _clean_speech_piece(candidate)
                            if clean:
                                pieces.append(clean)
                                first_phrase_emitted = True
                            # Advance pending past this sentence
                            pending = pending[sent_match.end():]
                        else:
                            break

                    # If no sentence boundary yet, but first phrase is long (>9 words) with a natural pause
                    if not first_phrase_emitted and not pieces:
                        words = pending.split()
                        if len(words) >= 9:
                            clause_match = re.search(r"^(.*?[\,\;\—\:])(?:\s+|$)", pending, flags=re.S)
                            if clause_match and len(clause_match.group(1).split()) >= 5:
                                clean = _clean_speech_piece(clause_match.group(1))
                                if clean:
                                    pieces.append(clean)
                                    first_phrase_emitted = True

                for piece in pieces:
                    if not piece:
                        continue
                    idx = stream_buffer.find(piece, spoken_chars)
                    if idx < 0:
                        spoken_chars = len(stream_buffer)
                    else:
                        spoken_chars = idx + len(piece)
                    if not chunker_recorded:
                        waterfall.chunker_ms = self.latency_hooks.now_ms()
                        chunker_recorded = True
                    tts_q.put_nowait(piece)

            async def _stream_llm(_pid: str) -> bool:
                nonlocal ttft_recorded, stream_buffer, pending_tool_calls
                async for chunk in self.llm_provider.generate_stream(
                    messages, llm_cfg, cancellation_token=self._llm_cancel
                ):
                    if self._llm_cancel.is_cancelled:
                        break
                    if not ttft_recorded:
                        waterfall.llm_ttft_ms = self.latency_hooks.now_ms()
                        ttft_recorded = True
                        if self.fsm.can_transition(SessionEvent.LLM_FIRST_TOKEN):
                            self.fsm.trigger(SessionEvent.LLM_FIRST_TOKEN)
                    if sc.enable_tool_loop and chunk.tool_calls:
                        pending_tool_calls.extend(chunk.tool_calls)
                    if chunk.text:
                        reply_parts.append(chunk.text)
                        stream_buffer += chunk.text
                        _enqueue_stable_speech(final=False)
                return True

            tts_consumer = asyncio.create_task(_consume_tts_queue())
            self._tts_task = tts_consumer
            self.three_point_cancel.register_task(tts_consumer)

            try:
                await self.failover_router.call_with_failover(
                    "llm", session_config.language, _stream_llm, first_chunk_timeout=20.0
                )
            except Exception as exc:
                logger.error("LLM provider chain failed; using offline mock", error=str(exc))
                user = next(
                    (m["content"] for m in reversed(messages) if m.get("role") == "user"),
                    "",
                )
                fallback = f"I heard you say: {user}. How can I help you today?"
                reply_parts.append(fallback)
                stream_buffer = fallback

            if pending_tool_calls and sc.enable_tool_loop:
                for tc in pending_tool_calls:
                    name = str(tc.get("function", {}).get("name") or tc.get("name") or "").strip()
                    raw_args = tc.get("function", {}).get("arguments") or tc.get("arguments") or {}
                    if isinstance(raw_args, str):
                        try:
                            arguments = json.loads(raw_args) if raw_args else {}
                        except Exception:
                            arguments = {}
                    else:
                        arguments = dict(raw_args) if raw_args else {}
                    if name:
                        tool_text = await _run_tool_with_filler(name, arguments)
                        reply_parts.append(tool_text)
                        stream_buffer += (" " + tool_text)

            _enqueue_stable_speech(final=True)
            await tts_q.put(None)
            try:
                await tts_consumer
            except asyncio.CancelledError:
                raise

            normalized = "".join(reply_parts) or "OK"
            norm_result = self.normalizer.normalize(normalized, language=session_config.language)
            normalized = getattr(norm_result, "text", None) or str(norm_result)

        if self.on_transcript:
            maybe = self.on_transcript("agent", normalized)
            if asyncio.iscoroutine(maybe):
                await maybe

        await self.redis_store.append_turn(
            session_config.session_id,
            {
                "speaker": "assistant",
                "text": normalized,
                "language": session_config.language,
            },
        )

        self.latency_collector.record_turn(waterfall)
        await self._emit_latency_telemetry(waterfall)
        if self._active_latency_turn_id == waterfall.turn_id:
            self._active_latency_turn_id = None
        if self.fsm.can_transition(SessionEvent.TTS_DRAINED):
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        self._turn_ends.append(time.monotonic())
        return normalized

    async def run_greeting(
        self, session_config: PipelineSessionConfig, phrase: str
    ) -> None:
        """Speak a synthetic greeting with a correlated, non-E2E latency trace."""
        self._playback_started = False
        waterfall = self.latency_hooks.start_turn(
            _metric_session_uuid(session_config.session_id)
        )
        self._active_latency_turn_id = waterfall.turn_id
        try:
            await self._finish_turn_tts([phrase], session_config, waterfall)
        finally:
            self.latency_collector.record_turn(waterfall)
            await self._emit_latency_telemetry(waterfall)
            if self._active_latency_turn_id == waterfall.turn_id:
                self._active_latency_turn_id = None

    async def _finish_turn_tts(
        self,
        sentences: list[str],
        session_config: PipelineSessionConfig,
        waterfall: Any,
    ) -> None:
        self._tts_task = asyncio.create_task(
            self._synthesize_streaming(sentences, session_config, waterfall)
        )
        self.three_point_cancel.register_task(self._tts_task)
        await self._tts_task

    async def finalize_session(
        self, session_config: PipelineSessionConfig, *, clear_hot_state: bool = True
    ) -> None:
        """Teardown: post-call enqueue, metering, optional Redis clear (WS path)."""
        if getattr(self, "_finalized_once", False):
            return
        self._finalized_once = True

        if self._egress_sender_task and not self._egress_sender_task.done():
            self._egress_sender_task.cancel()
            try:
                await self._egress_sender_task
            except asyncio.CancelledError:
                pass

        await self._close_live_stt()
        if self._vad_worker is not None:
            self._vad_worker.shutdown()
            self._vad_worker = None

        for provider in (self.llm_provider, self.tts_provider, self.stt_provider):
            close_fn = getattr(provider, "aclose", None)
            if close_fn:
                maybe = close_fn()
                if asyncio.iscoroutine(maybe):
                    await maybe

        if self.fsm.can_transition(SessionEvent.DISCONNECT):
            self.fsm.trigger(SessionEvent.DISCONNECT)

        raw_turns = await self.redis_store.get_turns(session_config.session_id)
        redacted_turns = self.redaction_service.redact_transcript(
            raw_turns, RedactionPolicy(redact_pii_in_transcript=True)
        )
        duration = max(0.01, time.monotonic() - self._started_at)
        self.usage_meter.record(
            session_config.tenant_id,
            session_config.session_id,
            "agent_sec",
            duration,
        )

        try:
            diarized = self._build_diarized_turns(redacted_turns)
            now_utc = datetime.now(timezone.utc)
            from post_call.models.recording import CallRecording

            record = CallRecord(
                tenant_id=parse_uuid(session_config.tenant_id, "tenant_id"),
                agent_id=parse_uuid(session_config.agent_id, "agent_id"),
                session_id=parse_uuid(session_config.session_id, "session_id"),
                caller_id=getattr(session_config.caller_id, "from_number", None),
                compliance_tier=session_config.compliance_tier,
                started_at=now_utc,
                ended_at=now_utc,
                turns=diarized,
                recording=CallRecording(
                    recording_s3_uri=f"s3://ucve-recordings/{session_config.session_id}.wav",
                    dual_channel=True,
                    duration_sec=duration,
                ),
            )
            await self.post_call_pipeline.enqueue(record)
        except UCVEError as exc:
            logger.warning("Skipped PostCallRecord (identity validation)", error=str(exc))
        except Exception as exc:
            logger.warning("Failed to enqueue PostCallRecord", error=str(exc))

        if clear_hot_state:
            await self.redis_store.clear_session(session_config.session_id)
        if hasattr(self.latency_collector, "clear_session"):
            self.latency_collector.clear_session()

        self.audit_writer.record(
            tenant_id=session_config.tenant_id,
            action="call_record_created",
            resource_type="session",
            resource_id=session_config.session_id,
            detail={"turn_count": len(redacted_turns)},
        )
        logger.info(
            "Pipeline session terminated cleanly", session_id=session_config.session_id
        )

    def _build_diarized_turns(
        self, turns: list[dict[str, Any]]
    ) -> list[DiarizedTurn]:
        base_ms = int((self._session_start_monotonic - self._started_at) * 1000)
        out: list[DiarizedTurn] = []
        for i, t in enumerate(turns):
            start = base_ms
            if i < len(self._turn_starts):
                start = int((self._turn_starts[i] - self._session_start_monotonic) * 1000)
            end = start + 1000
            if i < len(self._turn_ends):
                end = int((self._turn_ends[i] - self._session_start_monotonic) * 1000)
            out.append(
                DiarizedTurn(
                    speaker=t.get("speaker", "user"),
                    text=t.get("text", ""),
                    start_ms=max(0, start),
                    end_ms=max(start, end),
                )
            )
        return out

    async def run(
        self,
        session_config: PipelineSessionConfig,
        user_turns: list[str] | None = None,
    ) -> None:
        """Run session orchestration (test / batch path)."""
        logger.info("Pipeline session starting", session_id=session_config.session_id)
        self._started_at = time.monotonic()
        self._session_start_monotonic = self._started_at

        if session_config.compliance_tier == "hipaa" and not session_config.hipaa_baa_acknowledged:
            raise PermissionError(
                "HIPAA compliance requires signed BAA acknowledgment before cloud LLM execution."
            )

        turns = user_turns if user_turns is not None else ["Hello test call"]
        try:
            self.fsm.trigger(SessionEvent.SESSION_ADMITTED)
            for text in turns:
                await self.run_turn(session_config, text)
        finally:
            await self.finalize_session(session_config, clear_hot_state=False)


def build_providers(*, allow_null: bool = False) -> tuple[Any, Any, Any]:
    if allow_null:
        return NullSTTProvider(), NullLLMProvider(), NullTTSProvider()
    return GladiaSTTProvider(), GroqLLMProvider(), UpliftTTSProvider()
