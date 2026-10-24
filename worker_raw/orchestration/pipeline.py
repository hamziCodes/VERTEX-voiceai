"""UCVE Real-Time Pipeline Orchestrator."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import NAMESPACE_DNS, UUID, uuid5

from core.buffers.cancellation import AsyncioCancellationToken
from core.buffers.policy import OUTBOUND_TTS_POLICY, SENTENCE_BRIDGE_POLICY
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
from core.language.normalizer import TextNormalizer
from core.language.router import LanguageRouter
from core.language.streaming_chunker import StreamingSpeechChunker
from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from core.listening.barge_verify import BargeVerifyEngine
from core.listening.config import (
    FRAME_MS,
    ListeningPipelineConfig,
    SpeakingPipelineConfig,
)
from core.listening.speech_capture import SpeechCaptureEngine
from core.listening.vad_worker import VADWorker
from core.mcp.filler import ConversationalFillerSynth, FillerConfig
from core.metering.kinds import AGENT_SEC, LLM_TOKENS, STT_SEC, TTS_SEC
from core.metering.usage_meter import UsageMeter
from core.observability.logging import get_logger
from core.playback.turn_commit import PlayedTextCommit, TurnCommitTracker
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
from core.providers.exceptions import ProviderStreamInterruptedError
from core.providers.factory import (
    build_llm_provider,
    build_stt_provider,
    build_tts_provider,
    normalize_llm_provider,
    normalize_stt_provider,
    normalize_tts_provider,
)
from core.providers.failover import FailoverRouter, ProviderStreamDeadlines
from core.providers.interfaces.live_stt import BaseLiveSTTSession
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig
from core.providers.interfaces.stt import BaseSTTProvider, STTConfig
from core.providers.interfaces.tts import BaseTTSProvider, TTSConfig
from core.providers.live_stt_factory import build_live_stt_session
from core.providers.mode import provider_runtime_status
from core.providers.registry import ProviderRegistry
from core.rag.prompt_context import (
    KnowledgeContextService,
    RetrievalOutcome,
    build_prompt_messages,
)
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval
from core.session.redis_store import RedisSessionStore
from core.transport.resample_egress import StreamingEgressResampler
from core.types.audio import AudioFrame
from core.types.events import ControlEventType
from core.vad.silero_adapter import SileroVADAdapter
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.pipeline.enqueue import PostCallPipeline
from worker_raw.orchestration.latency_hooks import LatencyHooks
from worker_raw.orchestration.provider_binding import (
    BoundProviderChains,
    ProviderSessionBinder,
)
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
        provider_binder: ProviderSessionBinder | None = None,
    ) -> None:
        self.allow_testing_providers = allow_testing_providers
        self.on_audio_out = on_audio_out
        self.on_transcript = on_transcript
        self.tool_handler = tool_handler or PipelineToolHandler()
        self.latency_collector = latency_collector or LatencyCollector()
        self.latency_hooks = LatencyHooks(self.latency_collector)
        self.rag_retriever = rag_retriever or PgVectorRetriever()
        self.speculative_rag = SpeculativeRetrieval(self.rag_retriever)
        self.rag_context = KnowledgeContextService(
            self.rag_retriever, speculative=self.speculative_rag
        )
        self.post_call_pipeline = post_call_pipeline or PostCallPipeline()
        self.provider_binder = provider_binder
        self.bound_provider_chains: BoundProviderChains | None = None
        self.listening_config = ListeningPipelineConfig.from_env()
        self.speaking_config = SpeakingPipelineConfig.from_env()
        self.vad_adapter = SileroVADAdapter()
        self._apply_vad_timing()
        self.stt_provider: BaseSTTProvider = GladiaSTTProvider(
            mock_text=self.listening_config.stt_mock_text
        )
        self.llm_provider: BaseLLMProvider = GroqLLMProvider()
        self.tts_provider: BaseTTSProvider = UpliftTTSProvider(
            chunk_size_bytes=(
                self.speaking_config.tts_chunk_size_bytes
                if self.speaking_config.enable_speaking_hardening
                else 3200
            )
        )
        self._active_stt_id = "gladia"
        self._active_llm_id = "groq"
        self._active_tts_id = "uplift"
        self.stt_router = FailoverRouter(priority=["primary", "secondary"])
        self.llm_router = FailoverRouter(priority=["primary", "secondary"])
        self.tts_router = FailoverRouter(priority=["primary", "secondary"])
        self.failover_router = self.llm_router
        self.language_router = LanguageRouter()
        self.normalizer = TextNormalizer()
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
        self._stt_audio_sec = 0.0
        self._tts_audio_sec = 0.0
        self._session_start_monotonic = time.monotonic()
        self._turn_starts: list[float] = []
        self._turn_ends: list[float] = []
        self._ws_session: Any | None = None
        self._egress_queue: TypedAsyncQueue[tuple[int, bytes]] = TypedAsyncQueue(
            OUTBOUND_TTS_POLICY
        )
        self._egress_sender_task: asyncio.Task[None] | None = None
        self._egress_generation = 0
        self._llm_cancel = AsyncioCancellationToken()
        self._tts_cancel = AsyncioCancellationToken()
        self._playback_started = False
        self._finalized_once = False
        self._runtime_resources_closed = False
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
        # All sessions share a bounded executor; never create per-session VAD
        # threads or enqueue work on asyncio's unrelated default executor.
        self._vad_worker: VADWorker | None = VADWorker()
        self._live_stt: BaseLiveSTTSession | None = None
        self._live_stt_task: asyncio.Task[None] | None = None
        self._live_stt_status = "disabled"
        self._live_stt_start_lock = asyncio.Lock()
        self._live_stt_generation = 0
        self._live_stt_attempts = 0
        self._live_final_text: str = ""
        self._filler: ConversationalFillerSynth | None = None
        # Playback pause gate for barge verification (set => audio flows).
        self._playback_pause_event = asyncio.Event()
        self._playback_pause_event.set()
        self._barge_verify_task: asyncio.Task[None] | None = None
        self._active_latency_turn_id: UUID | None = None
        self._active_playback_turn_id: str | None = None
        self._turn_commit_tracker = TurnCommitTracker()
        self._pending_assistant_turns: dict[str, tuple[str, str]] = {}
        self._control_sequence = 0
        self._pending_clear_acks: dict[int, tuple[str, asyncio.Event]] = {}
        self._clear_ack_tasks: set[asyncio.Task[None]] = set()
        self._barge_lock = asyncio.Lock()
        self._interrupted_turn_ids: set[str] = set()
        # Always flush egress on three-point cancel (fixes ghost audio after barge).
        self.three_point_cancel.register_flush_callback(self._flush_egress_queue)

    @property
    def runtime_task_count(self) -> int:
        """Number of still-running tasks owned directly by this orchestrator."""
        tasks = {
            self._llm_task,
            self._tts_task,
            self._egress_sender_task,
            self._live_stt_task,
            self._barge_verify_task,
            *self._clear_ack_tasks,
            *self.three_point_cancel.active_tasks,
        }
        return sum(task is not None and not task.done() for task in tasks)

    async def shutdown_runtime_resources(self) -> None:
        """Idempotently stop tasks, streams, workers, and pooled provider clients."""
        if self._runtime_resources_closed:
            return
        self._llm_cancel.cancel()
        self._tts_cancel.cancel()
        if self._filler is not None:
            self._filler.cancel()
            self._filler = None

        await self.three_point_cancel.cancel_and_wait()
        await self._close_live_stt()

        current = asyncio.current_task()
        tasks = {
            task
            for task in (
                self._llm_task,
                self._tts_task,
                self._barge_verify_task,
                self._egress_sender_task,
                *self._clear_ack_tasks,
            )
            if task is not None and task is not current and not task.done()
        }
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._llm_task = None
        self._tts_task = None
        self._barge_verify_task = None
        self._egress_sender_task = None
        self._clear_ack_tasks.clear()
        self._pending_clear_acks.clear()
        self._turn_commit_tracker.discard_all()
        self._pending_assistant_turns.clear()
        self._active_playback_turn_id = None

        if self._vad_worker is not None:
            self._vad_worker.shutdown()
            self._vad_worker = None

        if self.bound_provider_chains is not None:
            await self.bound_provider_chains.aclose()
        else:
            seen: set[int] = set()
            for provider in (self.llm_provider, self.tts_provider, self.stt_provider):
                if id(provider) in seen:
                    continue
                seen.add(id(provider))
                close_fn = getattr(provider, "aclose", None)
                if close_fn:
                    try:
                        result = close_fn()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as exc:
                        logger.warning(
                            "Provider close failed during teardown",
                            provider=type(provider).__name__,
                            error_type=type(exc).__name__,
                        )
        self._runtime_resources_closed = True

    async def apply_provider_selection(
        self, session_config: PipelineSessionConfig
    ) -> None:
        """Swap providers from session config at session start only."""
        self.language_router.set_supported_languages(session_config.allowed_languages)
        configure_tools = getattr(self.tool_handler, "set_allowed_tools", None)
        if callable(configure_tools):
            configure_tools(session_config.tool_allowlist)

        if session_config.plan_authoritative:
            binder = self.provider_binder or ProviderSessionBinder.default(
                speaking_config=self.speaking_config,
                stt_mock_text=self.listening_config.stt_mock_text,
            )
            bound = await binder.bind(session_config)
            if self.bound_provider_chains is not None:
                await self.bound_provider_chains.aclose()
            self.bound_provider_chains = bound
            self.stt_provider = bound.stt[0].adapter
            self.llm_provider = bound.llm[0].adapter
            self.tts_provider = bound.tts[0].adapter
            self.stt_router = FailoverRouter(priority=list(bound.stt))
            self.llm_router = FailoverRouter(priority=list(bound.llm))
            self.tts_router = FailoverRouter(priority=list(bound.tts))
            self.failover_router = self.llm_router
            self._active_stt_id = bound.stt[0].identity.provider_id
            self._active_llm_id = bound.llm[0].identity.provider_id
            self._active_tts_id = bound.tts[0].identity.provider_id
            self._active_llm_model = bound.llm[0].identity.model
            logger.info(
                "Published provider chains bound",
                stt_routes=len(bound.stt),
                llm_routes=len(bound.llm),
                tts_routes=len(bound.tts),
            )
            return

        stt_id = normalize_stt_provider(session_config.stt_provider)
        llm_id = normalize_llm_provider(session_config.llm_provider)
        tts_id = normalize_tts_provider(session_config.tts_provider)
        session_config.stt_provider = stt_id
        session_config.llm_provider = llm_id
        session_config.tts_provider = tts_id

        if stt_id != self._active_stt_id:
            self.stt_provider = build_stt_provider(
                stt_id,
                api_key=None,
                mock_text=self.listening_config.stt_mock_text,
            )
            self._active_stt_id = stt_id

        llm_model_choice = getattr(session_config, "llm_model", None)
        if (
            llm_id != self._active_llm_id
            or getattr(self, "_active_llm_model", None) != llm_model_choice
        ):
            old = self.llm_provider
            self.llm_provider = build_llm_provider(
                llm_id, api_key=None, model=llm_model_choice
            )
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
                tts_id, api_key=None, speaking_config=self.speaking_config
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

    @staticmethod
    def _route_adapter(route: Any, fallback: Any) -> Any:
        return getattr(route, "adapter", fallback)

    @staticmethod
    def _synthetic_provider_reply_allowed() -> bool:
        return provider_runtime_status()["provider_mode"] == "mock"

    def _flush_egress_queue(self) -> None:
        """Drop any queued-but-unsent agent audio (three-point cancel: sender)."""
        dropped = 0
        while not self._egress_queue.empty():
            try:
                self._egress_queue.get_nowait()
                self._egress_queue.task_done()
                dropped += 1
            except Exception:
                break
        if dropped > 0:
            logger.info(
                "Flushed egress audio queue on barge-in", dropped_chunks=dropped
            )

    def attach_ws_session(self, session: Any) -> None:
        self._ws_session = session
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    def apply_language_vad_overrides(self, language: str) -> None:
        """Wire per-language VAD silence overrides from the language registry."""
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
                generation, pcm = await self._egress_queue.get()
            except asyncio.CancelledError:
                break
            try:
                # Block while playback is paused during a barge verification window.
                if not self._playback_pause_event.is_set():
                    try:
                        await self._playback_pause_event.wait()
                    except asyncio.CancelledError:
                        break
                # A barge-in increments the generation before flushing. This check
                # also rejects the chunk that a sender may already have dequeued.
                if generation != self._egress_generation:
                    continue
                if self.on_audio_out:
                    maybe = self.on_audio_out(pcm)
                    if asyncio.iscoroutine(maybe):
                        await maybe
            finally:
                self._egress_queue.task_done()

    def pause_playback(self) -> None:
        """Pause egress to the client (barge verify window)."""
        self._playback_pause_event.clear()

    def resume_playback(self) -> None:
        """Resume egress to the client after a false-alarm barge."""
        self._playback_pause_event.set()

    async def _ensure_egress_sender(self) -> None:
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    async def _emit_audio(
        self,
        pcm: bytes,
        waterfall: Any | None = None,
        *,
        generation: int | None = None,
    ) -> None:
        generation = self._egress_generation if generation is None else generation
        if generation != self._egress_generation:
            return
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
                            "audio.start",
                            {
                                "turn_id": str(waterfall.turn_id),
                                "server_send_ms": waterfall.server_send_ms,
                                "clock_domain": waterfall.clock_domain,
                                "recommended_prebuffer_ms": (
                                    self.speaking_config.egress_prebuffer_ms
                                ),
                            },
                        )
                    except Exception as exc:
                        logger.debug("Client audio.start notify failed", error=str(exc))
            if self.fsm.can_transition(SessionEvent.TTS_FIRST_BYTE):
                self.fsm.trigger(SessionEvent.TTS_FIRST_BYTE)
        await self._ensure_egress_sender()
        queue_wait_started = time.monotonic()
        await self._egress_queue.put((generation, pcm))
        if waterfall is not None:
            turn_id = str(waterfall.turn_id)
            if turn_id in self._pending_assistant_turns:
                self._turn_commit_tracker.add_audio(turn_id, len(pcm))
        queue_wait_ms = (time.monotonic() - queue_wait_started) * 1000
        if queue_wait_ms >= 5:
            logger.warning(
                "TTS egress backpressure",
                wait_ms=round(queue_wait_ms, 2),
                queue_size=self._egress_queue.qsize(),
                queue_high_water=self._egress_queue.high_watermark,
            )

    def _next_control_sequence(self) -> int:
        self._control_sequence += 1
        return self._control_sequence

    async def _notify_client_barge_in(
        self, reason: str = "barge_in_committed"
    ) -> int | None:
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return None
        turn_id = self._active_playback_turn_id
        try:
            barge_sequence = self._next_control_sequence()
            await transport.send_control_event(
                ControlEventType.BARGE_IN,
                {
                    "reason": reason,
                    "turn_id": turn_id,
                    "sequence": barge_sequence,
                },
            )
            clear_sequence = self._next_control_sequence()
            clear_event = asyncio.Event()
            self._pending_clear_acks[clear_sequence] = (turn_id or "", clear_event)
            await transport.send_control_event(
                ControlEventType.CLEAR_AUDIO,
                {
                    "reason": reason,
                    "turn_id": turn_id,
                    "sequence": clear_sequence,
                },
            )
            watchdog = asyncio.create_task(
                self._clear_audio_ack_watchdog(clear_sequence),
                name=f"clear-audio-ack:{clear_sequence}",
            )
            self._clear_ack_tasks.add(watchdog)
            watchdog.add_done_callback(self._clear_ack_tasks.discard)
            return clear_sequence
        except Exception as exc:
            logger.debug("Client barge_in notify failed", error=str(exc))
            return None

    async def _clear_audio_ack_watchdog(self, sequence: int) -> None:
        pending = self._pending_clear_acks.get(sequence)
        if pending is None:
            return
        turn_id, event = pending
        try:
            await asyncio.wait_for(event.wait(), timeout=0.5)
            return
        except TimeoutError:
            await self._commit_played_assistant(
                turn_id,
                played_audio_ms=0.0,
                complete=False,
            )
            await self._emit_degraded_event(
                "clear_audio_ack_timeout",
                {"turn_id": turn_id or None, "sequence": sequence},
            )
        finally:
            self._pending_clear_acks.pop(sequence, None)

    async def handle_clear_audio_ack(
        self,
        *,
        turn_id: str,
        sequence: int,
        played_audio_ms: float,
    ) -> bool:
        """Resolve one client buffer-clear request and commit only played speech."""
        pending = self._pending_clear_acks.get(sequence)
        if pending is None or pending[0] != turn_id:
            return False
        await self._commit_played_assistant(
            turn_id,
            played_audio_ms=max(0.0, played_audio_ms),
            complete=False,
        )
        pending[1].set()
        self._pending_clear_acks.pop(sequence, None)
        return True

    async def _settle_pending_clear_acks(self) -> None:
        """Bound the ordering wait before the interrupting user turn reads history."""
        for sequence, (turn_id, event) in list(self._pending_clear_acks.items()):
            try:
                await asyncio.wait_for(event.wait(), timeout=0.12)
            except TimeoutError:
                await self._commit_played_assistant(
                    turn_id,
                    played_audio_ms=0.0,
                    complete=False,
                )
                event.set()
            finally:
                self._pending_clear_acks.pop(sequence, None)

    async def handle_playback_drained(
        self, *, turn_id: str, played_audio_ms: float
    ) -> bool:
        """Commit a normally drained turn and release the FSM to listening."""
        if turn_id not in self._pending_assistant_turns:
            return False
        await self._commit_played_assistant(
            turn_id,
            played_audio_ms=max(0.0, played_audio_ms),
            complete=True,
        )
        if self.fsm.can_transition(SessionEvent.TTS_DRAINED):
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        return True

    async def _commit_played_assistant(
        self,
        turn_id: str,
        *,
        played_audio_ms: float,
        complete: bool,
    ) -> PlayedTextCommit:
        result = self._turn_commit_tracker.commit(
            turn_id,
            played_audio_ms=played_audio_ms,
            complete=complete,
        )
        metadata = self._pending_assistant_turns.pop(turn_id, None)
        if self._active_playback_turn_id == turn_id:
            self._active_playback_turn_id = None
        if metadata is not None and result.text:
            session_id, language = metadata
            if self.on_transcript:
                maybe = self.on_transcript("agent", result.text)
                if asyncio.iscoroutine(maybe):
                    await maybe
            await self.redis_store.append_turn(
                session_id,
                {
                    "speaker": "assistant",
                    "text": result.text,
                    "language": language,
                    "playback_complete": result.complete,
                },
            )
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is not None:
            try:
                await transport.send_control_event(
                    ControlEventType.PLAYED_TEXT_COMMIT,
                    {
                        "turn_id": turn_id,
                        "text": result.text,
                        "played_audio_ms": result.played_audio_ms,
                        "complete": result.complete,
                    },
                )
            except Exception as exc:
                logger.debug("Played-text commit notify failed", error=str(exc))
        return result

    async def _notify_audio_end(self, turn_id: str) -> None:
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await asyncio.wait_for(self._egress_queue.join(), timeout=2.0)
        except TimeoutError:
            await self._emit_degraded_event(
                "egress_drain_timeout",
                {"turn_id": turn_id},
            )
            return
        await transport.send_control_event(
            "audio.end",
            {
                "turn_id": turn_id,
                "generated_audio_ms": self._turn_commit_tracker.generated_audio_ms(
                    turn_id
                ),
            },
        )

    async def _emit_degraded_event(self, kind: str, details: dict[str, Any]) -> None:
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await transport.send_control_event(
                ControlEventType.DEGRADED_MODE,
                {"kind": kind, "recoverable": True, **details},
            )
        except Exception:
            pass

    async def _emit_latency_telemetry(self, waterfall: LatencyWaterfall) -> None:
        """Broadcast the canonical versioned latency payload to the client."""
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            payload = waterfall.to_metric_payload()
            payload["population"] = self.latency_collector.percentile_summary()
            await transport.send_control_event("metric.latency", payload)
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

    async def _emit_vad_state(self, *, speaking: bool, probability: float) -> None:
        """Emit VAD transitions without enabling per-frame debug telemetry."""
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await transport.send_control_event(
                ControlEventType.METRIC,
                {
                    "kind": "vad_state",
                    "speech": speaking,
                    "probability": round(float(probability), 4),
                },
            )
        except Exception as exc:
            logger.debug("Failed to emit VAD state", error=str(exc))

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
            await self.execute_immediate_barge_in(
                reason="Barge verify sustained speech"
            )

        await engine.run(
            pause=_pause,
            resume=_resume,
            commit=_commit,
            is_speaking=lambda: bool(self.vad_adapter.is_speaking),
        )

    async def execute_immediate_barge_in(
        self, reason: str = "VAD speech onset"
    ) -> None:
        """Atomically invalidate audio, clear the client, and stop turn producers."""
        async with self._barge_lock:
            turn_id = self._active_playback_turn_id or ""
            if turn_id and turn_id in self._interrupted_turn_ids:
                return
            if turn_id:
                self._interrupted_turn_ids.add(turn_id)

            logger.info(
                "Executing immediate barge-in",
                reason=reason,
                state=str(self.fsm.state),
                turn_id=turn_id or None,
            )
            if turn_id:
                self.latency_collector.cancel_turn(
                    UUID(turn_id),
                    reason="barge_in",
                )
            if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                self.fsm.trigger(SessionEvent.VAD_SPEECH_START)

            # Invalidate before any await so a sender-held chunk cannot escape.
            self._egress_generation += 1
            self.pause_playback()
            self._flush_egress_queue()
            await self._notify_client_barge_in(reason=reason)

            self._llm_cancel.cancel()
            self._tts_cancel.cancel()
            if self._filler is not None:
                self._filler.cancel()
                self._filler = None
            await self.three_point_cancel.cancel_and_wait()

            if self.fsm.can_transition(SessionEvent.BARGE_CONFIRMED):
                self.fsm.trigger(SessionEvent.BARGE_CONFIRMED)
            self.barge_in_controller.committed_count += 1
            self.resume_playback()
            if self._speech_capture is not None:
                self._speech_capture.begin_capture()
            self._capturing_speech = True
            await self._maybe_start_live_stt()

    async def prepare_live_stt(self) -> str:
        """Warm selected streaming STT before readiness with bounded startup."""
        if not self.listening_config.enable_streaming_stt:
            self._live_stt_status = "disabled"
            return self._live_stt_status
        if self._live_stt is not None and self._live_stt.is_live:
            return "ready"
        if self._live_stt_status == "batch_fallback":
            return self._live_stt_status
        async with self._live_stt_start_lock:
            if self._live_stt is not None and self._live_stt.is_live:
                return "ready"
            max_attempts = max(
                1,
                self.listening_config.stt_reconnect_max_attempts,
            )
            if self._live_stt_attempts >= max_attempts:
                self._live_stt_status = "failed"
                return self._live_stt_status
            cfg = (
                getattr(self._ws_session, "config", None) if self._ws_session else None
            )
            language = getattr(cfg, "language", "en") if cfg else "en"
            session = build_live_stt_session(
                self._active_stt_id,
                api_key=getattr(self.stt_provider, "api_key", None),
                model=(
                    self.bound_provider_chains.stt[0].identity.model
                    if self.bound_provider_chains is not None
                    else getattr(self.stt_provider, "model", None)
                ),
                language=language,
                endpointing=self.listening_config.gladia_endpointing,
                receive_partials=self.listening_config.gladia_receive_partials,
            )
            if session is None:
                self._live_stt_status = "batch_fallback"
                return self._live_stt_status
            self._live_stt_attempts += 1
            timeout = max(
                0.001,
                self.listening_config.stt_connect_timeout_ms / 1000.0,
            )
            try:
                started = await asyncio.wait_for(session.start(), timeout=timeout)
            except TimeoutError:
                await session.close()
                self._live_stt = None
                self._live_stt_status = "timeout"
                return self._live_stt_status
            except Exception as exc:
                await session.close()
                self._live_stt = None
                self._live_stt_status = "failed"
                logger.warning("Live STT warm-up failed", error=str(exc))
                return self._live_stt_status
            if not started:
                await session.close()
                self._live_stt = None
                self._live_stt_status = "batch_fallback"
                return self._live_stt_status
            self._live_stt = session
            self._live_stt_status = "ready"
            self._live_stt_generation += 1
            generation = self._live_stt_generation
            self._live_stt_task = asyncio.create_task(
                self._consume_live_stt(session, generation)
            )
            return self._live_stt_status

    async def _maybe_start_live_stt(self) -> None:
        await self.prepare_live_stt()

    async def _consume_live_stt(
        self,
        session: BaseLiveSTTSession,
        generation: int,
    ) -> None:
        try:
            async for transcript in session.transcripts():
                if (
                    session is not self._live_stt
                    or generation != self._live_stt_generation
                ):
                    return
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
                    enqueue = (
                        getattr(runner, "enqueue_voice_turn", None) if runner else None
                    )
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
            if session is self._live_stt:
                await session.close()
                self._live_stt = None
                self._live_stt_status = "failed"

    async def _maybe_speculate_rag(self, partial: str) -> None:
        if not self.listening_config.enable_rag_speculative:
            return
        cfg = getattr(self._ws_session, "config", None) if self._ws_session else None
        if cfg is None:
            return
        if (
            len(cfg.knowledge_base_ids) != 1
            or cfg.agent_config_version is None
            or not cfg.session_plan_hash
        ):
            return
        try:
            tenant_uuid = parse_uuid(cfg.tenant_id, "tenant_id")
            agent_uuid = parse_uuid(cfg.agent_id, "agent_id")
            base_uuid = parse_uuid(cfg.knowledge_base_ids[0], "knowledge_base_id")
        except Exception:
            return
        try:
            await self.speculative_rag.speculate(
                partial,
                tenant_uuid,
                agent_id=agent_uuid,
                agent_config_version=cfg.agent_config_version,
                knowledge_base_id=base_uuid,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("RAG speculation unavailable")

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

        if evt.speech_start and self.fsm.state in (
            SessionState.AGENT_SPEAKING,
            SessionState.PROCESSING_INFERENCE,
        ):
            if self._barge_verify is not None:
                if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                    self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
                if not self._barge_verify.is_verifying and (
                    self._barge_verify_task is None or self._barge_verify_task.done()
                ):
                    self._barge_verify_task = asyncio.create_task(
                        self._run_barge_verify()
                    )
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
                if (
                    not self._capturing_speech
                    and not self.listening_config.enable_quick_wins
                ):
                    self._speech_buffer = bytearray()
                self._capturing_speech = True
            else:
                self._capturing_speech = self._speech_capture.capturing
            await self._emit_vad_state(speaking=True, probability=evt.probability)
            await self._maybe_start_live_stt()

        capturing = (
            self._capturing_speech
            or (self._speech_capture is not None and self._speech_capture.capturing)
            or self.fsm.state
            in (
                SessionState.USER_SPEAKING,
                SessionState.BARGE_IN_INTERRUPTED,
            )
        )

        if capturing and evt.probability > 0.5:
            self._last_acoustic_speech_ms = self.latency_hooks.now_ms()

        # Always stream mic audio into the live Gladia session while it is up.
        # Legacy agents keep one live socket for the whole call; gating only on
        # "capturing" dropped frames around VAD edges and starved STT.
        sent_to_stt = False
        if frame.pcm16 and self._live_stt is not None and self._live_stt.is_live:
            if capturing or not agent_speaking:
                await self._live_stt.send_audio(frame.pcm16)
                sent_to_stt = True

        if capturing and frame.pcm16:
            sent_to_stt = True
            if self._speech_capture is None:
                max_buf = 512 * 1024
                if len(self._speech_buffer) + len(frame.pcm16) <= max_buf:
                    self._speech_buffer.extend(frame.pcm16)

        if sent_to_stt:
            self._stt_audio_sec += frame.duration_ms / 1000.0

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
            await self._emit_vad_state(speaking=False, probability=evt.probability)

        await self._emit_debug_listening(evt, frame)
        return evt

    async def transcribe_speech_buffer(
        self, session_config: PipelineSessionConfig
    ) -> str:
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

        def _transcribe(route: Any) -> AsyncIterator[Any]:
            adapter = self._route_adapter(route, self.stt_provider)
            return cast(
                AsyncIterator[Any], adapter.transcribe_stream(_audio_iter(), cfg)
            )

        text = ""
        if self.bound_provider_chains is not None:
            async for transcript in self.stt_router.stream_with_failover(
                "stt",
                session_config.language,
                _transcribe,
                deadlines=ProviderStreamDeadlines(
                    first_item_seconds=15.0,
                    idle_seconds=5.0,
                    overall_seconds=30.0,
                ),
                is_committed=lambda item: bool(item.text),
            ):
                if transcript.text:
                    text = transcript.text
        else:
            async for transcript in _transcribe("primary"):
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
        self,
        sentences: list[str],
        session_config: PipelineSessionConfig,
        waterfall: Any,
    ) -> None:
        voice = session_config.tts_voice_id or "default"
        turn_id = str(waterfall.turn_id)
        generation = self._egress_generation
        ttfb_recorded = False
        audio_committed = False
        deadlines = ProviderStreamDeadlines(
            first_item_seconds=max(
                0.001, self.speaking_config.tts_first_chunk_timeout_ms / 1000
            ),
            idle_seconds=max(
                0.001, self.speaking_config.tts_inter_chunk_timeout_ms / 1000
            ),
            overall_seconds=max(
                0.001, self.speaking_config.tts_overall_timeout_ms / 1000
            ),
        )
        for sentence in sentences:
            if self._tts_cancel.is_cancelled or self.three_point_cancel.cancelled:
                break
            if turn_id in self._pending_assistant_turns:
                self._turn_commit_tracker.start_segment(turn_id, sentence)
            cfg = TTSConfig(voice_id=voice, sample_rate=16000)

            def _provider_stream(
                route: Any,
                sentence: str = sentence,
                cfg: TTSConfig = cfg,
            ) -> AsyncIterator[Any]:
                adapter = self._route_adapter(route, self.tts_provider)
                return cast(
                    AsyncIterator[Any],
                    adapter.synthesize_stream(
                        sentence, cfg, cancellation_token=self._tts_cancel
                    ),
                )

            source_rate: int | None = None
            resampler: StreamingEgressResampler | None = None
            try:
                provider_stream = self.tts_router.stream_with_failover(
                    "tts",
                    session_config.language,
                    _provider_stream,
                    deadlines=deadlines,
                    is_committed=lambda item: bool(item.pcm_data),
                )
                async for chunk in provider_stream:
                    if self._tts_cancel.is_cancelled:
                        break
                    if chunk.pcm_data:
                        if not ttfb_recorded:
                            waterfall.tts_ttfb_ms = self.latency_hooks.now_ms()
                            ttfb_recorded = True
                        native = int(
                            getattr(chunk, "native_sample_rate", 16000) or 16000
                        )
                        if source_rate is None:
                            source_rate = native
                            resampler = StreamingEgressResampler(native, 16000)
                        elif native != source_rate:
                            raise ValueError(
                                "TTS sample rate changed inside one speech chunk."
                            )
                        assert resampler is not None
                        pcm = resampler.process(chunk.pcm_data)
                        # Separates silent vendor PCM from client playback bugs.
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
                            self._tts_pcm_logged = (
                                getattr(self, "_tts_pcm_logged", 0) + 1
                            )
                        if pcm:
                            self._tts_audio_sec += len(pcm) / (2 * 16000)
                            await self._emit_audio(
                                pcm,
                                waterfall,
                                generation=generation,
                            )
                            audio_committed = True
                if resampler is None and not self._tts_cancel.is_cancelled:
                    raise ValueError("TTS provider completed without audio.")
                if resampler is not None and not self._tts_cancel.is_cancelled:
                    tail = resampler.flush()
                    if tail:
                        self._tts_audio_sec += len(tail) / (2 * 16000)
                        await self._emit_audio(
                            tail,
                            waterfall,
                            generation=generation,
                        )
                        audio_committed = True
            except Exception as exc:
                logger.error(
                    "TTS stream failed",
                    error_type=type(exc).__name__,
                    audio_committed=audio_committed,
                )
                if audio_committed:
                    await self._emit_tts_interruption("provider_stream_failed")
                    return
                await self._emit_tts_interruption("tts_unavailable")
                return

    async def _emit_tts_interruption(self, reason: str) -> None:
        """Tell capable clients that committed speech ended unexpectedly."""
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await transport.send_control_event(
                ControlEventType.DEGRADED_MODE,
                {
                    "kind": "tts_interrupted",
                    "recoverable": True,
                    "reason": reason[:160],
                },
            )
        except Exception as exc:
            logger.debug("Client TTS interruption notify failed", error=str(exc))

    async def _emit_rag_degraded(self, outcome: RetrievalOutcome) -> None:
        """Expose a safe retrieval status without document or query content."""
        session = self._ws_session
        transport = getattr(session, "transport", None) if session is not None else None
        if transport is None:
            return
        try:
            await transport.send_control_event(
                ControlEventType.DEGRADED_MODE,
                {
                    "kind": "knowledge_retrieval",
                    "recoverable": True,
                    "status": outcome.status,
                    "category": outcome.error_category,
                },
            )
        except Exception:
            logger.debug("Client RAG degradation notify failed")

    async def run_turn(
        self, session_config: PipelineSessionConfig, user_text: str
    ) -> str:
        """Execute one STT→RAG→LLM/Tool→norm→TTS turn with latency tracing."""
        await self._settle_pending_clear_acks()
        turn_start = time.monotonic()
        self._turn_starts.append(turn_start)
        self._playback_started = False
        self._egress_queue.reset_metrics()
        self._tts_pcm_logged = 0
        self._tts_cancel = AsyncioCancellationToken()
        self._llm_cancel = AsyncioCancellationToken()
        self.three_point_cancel.reset()
        self.three_point_cancel.register_flush_callback(self._flush_egress_queue)
        current_turn_task = asyncio.current_task()
        if current_turn_task is not None:
            self._llm_task = current_turn_task
            self.three_point_cancel.register_task(current_turn_task)

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
        turn_id = str(waterfall.turn_id)
        self._active_playback_turn_id = turn_id
        self._turn_commit_tracker.begin_turn(turn_id)
        self._pending_assistant_turns[turn_id] = (
            session_config.session_id,
            session_config.language,
        )
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
        elif self.fsm.state == SessionState.AGENT_SPEAKING and self._ws_session is None:
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        elif self.fsm.state == SessionState.BARGE_IN_INTERRUPTED:
            # Interrupted turn is already processing or remains until STT final.
            pass

        if self.fsm.state == SessionState.LISTENING:
            self.fsm.trigger(SessionEvent.STT_FINAL)
        elif self.fsm.state == SessionState.BARGE_IN_INTERRUPTED:
            if self.fsm.can_transition(SessionEvent.STT_FINAL):
                self.fsm.trigger(SessionEvent.STT_FINAL)

        rag_chunks = []
        try:
            tenant_uuid = parse_uuid(session_config.tenant_id, "tenant_id")
        except UCVEError:
            if len(session_config.tenant_id) >= 35:
                raise
            tenant_uuid = None
        if tenant_uuid is not None and session_config.knowledge_base_ids:
            try:
                agent_uuid = parse_uuid(session_config.agent_id, "agent_id")
                retrieval = await self.rag_context.retrieve(
                    query=user_text,
                    tenant_id=tenant_uuid,
                    agent_id=agent_uuid,
                    agent_config_version=session_config.agent_config_version or 0,
                    plan_hash=session_config.session_plan_hash or "",
                    knowledge_base_ids=session_config.knowledge_base_ids,
                )
                waterfall.rag_retrieve_ms = self.latency_hooks.now_ms()
                waterfall.rag_status = retrieval.status
                waterfall.rag_result_count = retrieval.result_count
                waterfall.rag_cache_hit = retrieval.cache_hit
                waterfall.rag_soft_budget_exceeded = retrieval.soft_budget_exceeded
                waterfall.rag_error_category = retrieval.error_category
                rag_chunks = retrieval.chunks
                if retrieval.error_category is not None:
                    logger.warning(
                        "RAG retrieval degraded", category=retrieval.error_category
                    )
                    await self._emit_rag_degraded(retrieval)
            except asyncio.CancelledError:
                raise
            except Exception:
                waterfall.rag_retrieve_ms = self.latency_hooks.now_ms()
                waterfall.rag_status = "error"
                waterfall.rag_error_category = "runtime_retrieval_error"
                logger.warning(
                    "RAG retrieval degraded", category="runtime_retrieval_error"
                )

        prompt_str = (
            getattr(session_config, "system_prompt", None) or ""
        ).strip() or "You are a helpful voice agent."
        messages = build_prompt_messages(
            system_prompt=prompt_str,
            prior_turns=prior_turns,
            user_text=user_text,
            chunks=rag_chunks,
        )

        executed_tool_calls: set[str] = set()

        async def _run_tool_with_filler(
            tool_name: str,
            arguments: dict[str, Any],
            *,
            call_id: str | None = None,
        ) -> str | None:
            canonical_arguments = json.dumps(
                arguments,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            signature = f"signature:{tool_name}:{canonical_arguments}"
            identities = {signature}
            if call_id:
                identities.add(f"id:{call_id}")
            if executed_tool_calls.intersection(identities):
                logger.warning("Duplicate tool call suppressed", tool=tool_name)
                return None
            executed_tool_calls.update(identities)

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
                tool_res = await self.tool_handler.handle_tool_call(
                    tool_name, arguments
                )
                if self.fsm.can_transition(SessionEvent.TOOL_RESULT):
                    self.fsm.trigger(SessionEvent.TOOL_RESULT)
            finally:
                if self._filler is not None:
                    self._filler.cancel()
                    self._filler = None
            if filler_phrase:
                await self._finish_turn_tts(
                    filler_phrase[:1], session_config, waterfall
                )
            return str(tool_res.get("content", "Tool executed."))

        if user_text.startswith("tool:"):
            tool_name = user_text.split(":", 1)[1].strip()
            normalized = await _run_tool_with_filler(tool_name, {}) or ""
            if normalized:
                await self._finish_turn_tts([normalized], session_config, waterfall)
        else:
            default_m = (
                "gemini-2.5-flash"
                if self._active_llm_id == "gemini"
                else "openai/gpt-oss-120b"
            )
            model = (
                getattr(session_config, "llm_model", None)
                or getattr(self, "_active_llm_model", None)
                or default_m
            )
            llm_cfg = LLMConfig(model=model)
            reply_parts: list[str] = []
            ttft_recorded = False
            chunker_recorded = False
            pending_tool_calls: list[dict[str, Any]] = []
            speech_chunker = StreamingSpeechChunker.for_language(
                session_config.language,
                first_chunk_words_override=sc.chunker_first_words,
                min_chunk_words=sc.chunker_min_words,
            )
            tts_q: asyncio.Queue[tuple[str, float] | None] = asyncio.Queue(
                maxsize=SENTENCE_BRIDGE_POLICY.maxsize
            )
            tts_queue_high_water = 0
            tts_queue_max_age_ms = 0.0

            async def _consume_tts_queue() -> None:
                nonlocal tts_queue_max_age_ms
                while True:
                    item = await tts_q.get()
                    if item is None:
                        return
                    text, enqueued_at = item
                    tts_queue_max_age_ms = max(
                        tts_queue_max_age_ms,
                        (time.monotonic() - enqueued_at) * 1000,
                    )
                    await self._synthesize_streaming([text], session_config, waterfall)

            async def _enqueue_speech_chunks(chunks: list[Any]) -> None:
                nonlocal chunker_recorded, tts_queue_high_water
                for speech_chunk in chunks:
                    normalized_chunk = self.normalizer.normalize(
                        speech_chunk.text, language=session_config.language
                    )
                    piece = getattr(normalized_chunk, "text", "").strip()
                    if not piece:
                        continue
                    if not chunker_recorded:
                        waterfall.chunker_ms = self.latency_hooks.now_ms()
                        chunker_recorded = True
                    while True:
                        if tts_consumer.done():
                            await tts_consumer
                        try:
                            await asyncio.wait_for(
                                tts_q.put((piece, time.monotonic())), timeout=0.1
                            )
                            break
                        except TimeoutError:
                            if self._llm_cancel.is_cancelled:
                                raise asyncio.CancelledError() from None
                    tts_queue_high_water = max(tts_queue_high_water, tts_q.qsize())

            def _stream_llm(route: Any) -> AsyncIterator[Any]:
                adapter = self._route_adapter(route, self.llm_provider)
                return cast(
                    AsyncIterator[Any],
                    adapter.generate_stream(
                        messages, llm_cfg, cancellation_token=self._llm_cancel
                    ),
                )

            async def _consume_llm_stream() -> None:
                nonlocal ttft_recorded, pending_tool_calls
                stream = self.llm_router.stream_with_failover(
                    "llm",
                    session_config.language,
                    _stream_llm,
                    deadlines=ProviderStreamDeadlines(
                        first_item_seconds=10.0,
                        idle_seconds=10.0,
                        overall_seconds=60.0,
                    ),
                    is_committed=lambda item: bool(item.text or item.tool_calls),
                )
                async for chunk in stream:
                    if self._llm_cancel.is_cancelled:
                        break
                    if chunk.total_tokens is not None:
                        await self.usage_meter.arecord(
                            session_config.tenant_id,
                            session_config.session_id,
                            LLM_TOKENS,
                            float(chunk.total_tokens),
                            event_key=(
                                f"{session_config.session_id}:llm_tokens:"
                                f"{waterfall.turn_id}"
                            ),
                            unit="tokens",
                            provider_id=chunk.provider_id or self._active_llm_id,
                            provider_request_id=chunk.provider_request_id,
                            metadata={
                                "prompt_tokens": chunk.prompt_tokens,
                                "completion_tokens": chunk.completion_tokens,
                            },
                        )
                    if not ttft_recorded:
                        waterfall.llm_ttft_ms = self.latency_hooks.now_ms()
                        ttft_recorded = True
                        if self.fsm.can_transition(SessionEvent.LLM_FIRST_TOKEN):
                            self.fsm.trigger(SessionEvent.LLM_FIRST_TOKEN)
                    if sc.enable_tool_loop and chunk.tool_calls:
                        pending_tool_calls.extend(chunk.tool_calls)
                    if chunk.text:
                        reply_parts.append(chunk.text)
                        await _enqueue_speech_chunks(speech_chunker.push(chunk.text))

            tts_consumer = asyncio.create_task(_consume_tts_queue())
            self._tts_task = tts_consumer
            self.three_point_cancel.register_task(tts_consumer)

            try:
                await _consume_llm_stream()
            except ProviderStreamInterruptedError as exc:
                await tts_q.put(None)
                await tts_consumer
                logger.error(
                    "LLM stream interrupted after output commit",
                    provider=exc.failure.provider_id,
                    category=exc.failure.category.value,
                    committed_items=exc.committed_items,
                )
                raise
            except Exception as exc:
                if not self._synthetic_provider_reply_allowed():
                    await tts_q.put(None)
                    await tts_consumer
                    logger.error(
                        "LLM provider chain exhausted",
                        error_type=type(exc).__name__,
                    )
                    raise
                logger.error(
                    "LLM provider chain failed; using offline mock",
                    error_type=type(exc).__name__,
                )
                user = next(
                    (
                        m["content"]
                        for m in reversed(messages)
                        if m.get("role") == "user"
                    ),
                    "",
                )
                fallback = f"I heard you say: {user}. How can I help you today?"
                fallback_delta = (" " if reply_parts else "") + fallback
                reply_parts.append(fallback_delta)
                await _enqueue_speech_chunks(speech_chunker.push(fallback_delta))

            if pending_tool_calls and sc.enable_tool_loop:
                for tc in pending_tool_calls:
                    name = str(
                        tc.get("function", {}).get("name") or tc.get("name") or ""
                    ).strip()
                    raw_args = (
                        tc.get("function", {}).get("arguments")
                        or tc.get("arguments")
                        or {}
                    )
                    if isinstance(raw_args, str):
                        try:
                            arguments = json.loads(raw_args) if raw_args else {}
                        except Exception:
                            arguments = {}
                    else:
                        arguments = dict(raw_args) if raw_args else {}
                    if name:
                        tool_text = await _run_tool_with_filler(
                            name,
                            arguments,
                            call_id=str(tc.get("id") or "").strip() or None,
                        )
                        if tool_text is None:
                            continue
                        tool_delta = " " + tool_text
                        reply_parts.append(tool_delta)
                        await _enqueue_speech_chunks(speech_chunker.push(tool_delta))

            await _enqueue_speech_chunks(speech_chunker.flush())
            await tts_q.put(None)
            try:
                await tts_consumer
            except asyncio.CancelledError:
                raise
            logger.info(
                "TTS text queue drained",
                high_water=tts_queue_high_water,
                max_age_ms=round(tts_queue_max_age_ms, 2),
                egress_high_water=self._egress_queue.high_watermark,
            )

            normalized = "".join(reply_parts) or "OK"
            norm_result = self.normalizer.normalize(
                normalized, language=session_config.language
            )
            normalized = getattr(norm_result, "text", None) or str(norm_result)

        if self._ws_session is None:
            await self._commit_played_assistant(
                turn_id,
                played_audio_ms=self._turn_commit_tracker.generated_audio_ms(turn_id),
                complete=True,
            )
        else:
            await self._notify_audio_end(turn_id)

        self.latency_collector.record_turn(waterfall)
        await self._emit_latency_telemetry(waterfall)
        if self._active_latency_turn_id == waterfall.turn_id:
            self._active_latency_turn_id = None
        if self._ws_session is None and self.fsm.can_transition(
            SessionEvent.TTS_DRAINED
        ):
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

        await self.shutdown_runtime_resources()

        if self.fsm.can_transition(SessionEvent.DISCONNECT):
            self.fsm.trigger(SessionEvent.DISCONNECT)

        raw_turns = await self.redis_store.get_turns(session_config.session_id)
        redacted_turns = self.redaction_service.redact_transcript(
            raw_turns, RedactionPolicy(redact_pii_in_transcript=True)
        )
        duration = max(0.01, time.monotonic() - self._started_at)
        await self.usage_meter.arecord(
            session_config.tenant_id,
            session_config.session_id,
            AGENT_SEC,
            duration,
            event_key=f"{session_config.session_id}:agent_sec:final",
            unit="seconds",
        )
        await self.usage_meter.arecord(
            session_config.tenant_id,
            session_config.session_id,
            STT_SEC,
            self._stt_audio_sec,
            event_key=f"{session_config.session_id}:stt_sec:final",
            unit="seconds",
            provider_id=self._active_stt_id,
        )
        await self.usage_meter.arecord(
            session_config.tenant_id,
            session_config.session_id,
            TTS_SEC,
            self._tts_audio_sec,
            event_key=f"{session_config.session_id}:tts_sec:final",
            unit="seconds",
            provider_id=self._active_tts_id,
        )

        try:
            diarized = self._build_diarized_turns(redacted_turns)
            now_utc = datetime.now(UTC)
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
            logger.warning(
                "Skipped PostCallRecord (identity validation)", error=str(exc)
            )
        except Exception as exc:
            logger.warning("Failed to enqueue PostCallRecord", error=str(exc))

        if clear_hot_state:
            await self.redis_store.clear_session(session_config.session_id)
        if hasattr(self.latency_collector, "clear_session"):
            self.latency_collector.clear_session()

        await self.audit_writer.arecord(
            tenant_id=session_config.tenant_id,
            action="call_record_created",
            resource_type="session",
            resource_id=session_config.session_id,
            detail={"turn_count": len(redacted_turns)},
        )
        logger.info(
            "Pipeline session terminated cleanly", session_id=session_config.session_id
        )

    def _build_diarized_turns(self, turns: list[dict[str, Any]]) -> list[DiarizedTurn]:
        base_ms = int((self._session_start_monotonic - self._started_at) * 1000)
        out: list[DiarizedTurn] = []
        for i, t in enumerate(turns):
            start = base_ms
            if i < len(self._turn_starts):
                start = int(
                    (self._turn_starts[i] - self._session_start_monotonic) * 1000
                )
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

        if (
            session_config.compliance_tier == "hipaa"
            and not session_config.hipaa_baa_acknowledged
        ):
            raise PermissionError(
                "HIPAA compliance requires signed BAA acknowledgment before "
                "cloud LLM execution."
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
