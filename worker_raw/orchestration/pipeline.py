"""UCVE Real-Time Pipeline Orchestrator."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import NAMESPACE_DNS, UUID, uuid5

from core.buffers.cancellation import AsyncioCancellationToken
from core.buffers.policy import INBOUND_MIC_POLICY, OUTBOUND_TTS_POLICY
from core.buffers.typed_queue import TypedAsyncQueue
from core.compliance.audit.writer import AuditWriter
from core.compliance.redaction import RedactionService
from core.compliance.redaction_policy import RedactionPolicy
from core.compliance.tenant_profile import (
    TenantComplianceProfileLoader,
    assert_cloud_llm_allowed,
)
from core.errors.structured import StructuredError
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
from core.latency.collector import LatencyCollector
from core.mcp.orchestrator import ToolOrchestrator
from core.metering.usage_meter import UsageMeter
from core.observability.logging import get_logger
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.null_llm import NullLLMProvider
from core.providers.adapters.null_stt import NullSTTProvider
from core.providers.adapters.null_tts import NullTTSProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.failover import FailoverRouter
from core.providers.interfaces.llm import LLMConfig, LLMStreamChunk
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.providers.registry import ProviderRegistry
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval
from core.runtime.env import is_test_env
from core.session.redis_store import RedisSessionStore
from core.types.audio import AudioFrame
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
ProviderRegistry.register_provider_class("groq", GroqLLMProvider)
ProviderRegistry.register_provider_class("uplift", UpliftTTSProvider)


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
        self.vad_adapter = SileroVADAdapter()
        self.stt_provider = GladiaSTTProvider()
        self.llm_provider = GroqLLMProvider()
        self.tts_provider = UpliftTTSProvider()
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

    def attach_ws_session(self, session: Any) -> None:
        self._ws_session = session
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    async def _egress_sender_loop(self) -> None:
        while True:
            try:
                pcm = await self._egress_queue.get()
            except asyncio.CancelledError:
                break
            if self.on_audio_out:
                maybe = self.on_audio_out(pcm)
                if asyncio.iscoroutine(maybe):
                    await maybe

    async def _ensure_egress_sender(self) -> None:
        if self._egress_sender_task is None or self._egress_sender_task.done():
            self._egress_sender_task = asyncio.create_task(self._egress_sender_loop())

    async def _emit_audio(self, pcm: bytes, waterfall: Any | None = None) -> None:
        if not self._playback_started:
            self._playback_started = True
            if waterfall is not None:
                waterfall.playback_start_ms = self.latency_hooks.now_ms()
            if self.fsm.can_transition(SessionEvent.TTS_FIRST_BYTE):
                self.fsm.trigger(SessionEvent.TTS_FIRST_BYTE)
        await self._ensure_egress_sender()
        await self._egress_queue.put(pcm)

    async def process_frame_async(self, frame: AudioFrame) -> Any:
        """Run VAD off the event loop; drive barge-in on speech_start."""
        evt = await asyncio.to_thread(self.vad_adapter.process_frame, frame)
        if evt.speech_start:
            if self.fsm.state == SessionState.AGENT_SPEAKING:
                if self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                    self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
                result = self.barge_in_controller._commit_barge_in(
                    reason="VAD speech during agent TTS"
                )
                _ = result
                self.three_point_cancel.execute_cancel_and_flush()
            elif self.fsm.can_transition(SessionEvent.VAD_SPEECH_START):
                self.fsm.trigger(SessionEvent.VAD_SPEECH_START)
                if not self._capturing_speech:
                    self._speech_buffer = bytearray()
                self._capturing_speech = True
        if (
            self._capturing_speech
            or self.fsm.state in (SessionState.USER_SPEAKING, SessionState.BARGE_IN_INTERRUPTED)
        ) and frame.pcm16:
            max_buf = 512 * 1024
            if len(self._speech_buffer) + len(frame.pcm16) <= max_buf:
                self._speech_buffer.extend(frame.pcm16)
        if evt.speech_end:
            if self.fsm.state in (SessionState.USER_SPEAKING, SessionState.BARGE_IN_INTERRUPTED):
                if self.fsm.can_transition(SessionEvent.VAD_SPEECH_END):
                    self.fsm.trigger(SessionEvent.VAD_SPEECH_END)
            if self._capturing_speech:
                self._capturing_speech = False
                self._speech_end_pending = True
        return evt

    async def transcribe_speech_buffer(self, session_config: PipelineSessionConfig) -> str:
        """Run STT on buffered mic audio after VAD speech_end."""
        if not self._speech_buffer:
            return ""

        pcm = bytes(self._speech_buffer)
        self._speech_buffer = bytearray()

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

    def process_frame(self, frame: AudioFrame) -> Any:
        return self.vad_adapter.process_frame(frame)

    async def cancel_tts(self) -> None:
        self._tts_cancel.cancel()
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass

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
                        await self._emit_audio(chunk.pcm_data, waterfall)
                return True

            try:
                await self.failover_router.call_with_failover(
                    "tts", session_config.language, _invoke
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
        self._tts_cancel = AsyncioCancellationToken()
        self._llm_cancel = AsyncioCancellationToken()
        self.three_point_cancel.reset()

        interrupted = self.barge_in_controller.next_turn_input()
        if interrupted:
            user_text = interrupted

        waterfall = self.latency_hooks.start_turn(
            _metric_session_uuid(session_config.session_id)
        )
        waterfall.stt_final_ms = self.latency_hooks.now_ms()

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

        await self.redis_store.append_turn(
            session_config.session_id,
            {"speaker": "user", "text": user_text, "language": session_config.language},
        )
        if self.fsm.state == SessionState.CONNECTING:
            self.fsm.trigger(SessionEvent.SESSION_ADMITTED)
        elif self.fsm.state == SessionState.AGENT_SPEAKING:
            self.fsm.trigger(SessionEvent.TTS_DRAINED)

        if self.fsm.state == SessionState.LISTENING:
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
        messages = [
            {"role": "system", "content": f"{prompt_str}\n{rag_context}".strip()},
            {"role": "user", "content": user_text},
        ]

        if user_text.startswith("tool:"):
            self.fsm.trigger(SessionEvent.TOOL_CALL_START)
            tool_name = user_text.split(":", 1)[1].strip()
            tool_res = await self.tool_handler.handle_tool_call(tool_name, {})
            self.fsm.trigger(SessionEvent.TOOL_RESULT)
            normalized = tool_res.get("content", "Tool executed.")
            await self._finish_turn_tts([normalized], session_config, waterfall)
        else:
            model = session_config.llm_model or "llama-3.3-70b-versatile"
            llm_cfg = LLMConfig(model=model)
            sentences: list[str] = []
            tts_started = False
            tts_consumer: asyncio.Task[None] | None = None
            reply_parts: list[str] = []
            ttft_recorded = False
            stream_buffer = ""

            async def _consume_sentences() -> None:
                await self._synthesize_streaming(sentences, session_config, waterfall)

            async def _stream_llm(_pid: str) -> bool:
                nonlocal ttft_recorded, tts_started, tts_consumer, stream_buffer
                async for chunk in self.llm_provider.generate_stream(
                    messages, llm_cfg, cancellation_token=self._llm_cancel
                ):
                    if self._llm_cancel.is_cancelled:
                        break
                    if not ttft_recorded:
                        waterfall.llm_ttft_ms = self.latency_hooks.now_ms()
                        ttft_recorded = True
                    if chunk.text:
                        reply_parts.append(chunk.text)
                        stream_buffer += chunk.text
                        parts = self.chunker.chunk(stream_buffer)
                        if len(parts) > len(sentences):
                            sentences.extend(parts[len(sentences) :])
                            if not tts_started and sentences:
                                tts_started = True
                                tts_consumer = asyncio.create_task(_consume_sentences())
                                self._tts_task = tts_consumer
                                self.three_point_cancel.register_task(tts_consumer)
                return True

            try:
                await self.failover_router.call_with_failover(
                    "llm", session_config.language, _stream_llm
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
                sentences.extend(self.chunker.chunk(stream_buffer))

            if not tts_started and sentences:
                tts_consumer = asyncio.create_task(_consume_sentences())
                self._tts_task = tts_consumer
                self.three_point_cancel.register_task(tts_consumer)

            if tts_consumer:
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
        if self.fsm.can_transition(SessionEvent.TTS_DRAINED):
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        self._turn_ends.append(time.monotonic())
        return normalized

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
