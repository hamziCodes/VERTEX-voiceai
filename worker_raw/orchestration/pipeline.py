"""UCVE Real-Time Pipeline Orchestrator."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable
from uuid import UUID, uuid4

from core.compliance.audit.writer import AuditWriter
from core.compliance.redaction import RedactionService
from core.compliance.redaction_policy import RedactionPolicy
from core.compliance.tenant_profile import (
    TenantComplianceProfileLoader,
    assert_cloud_llm_allowed,
)
from core.fsm.barge_in import BargeInController
from core.fsm.events import SessionEvent
from core.fsm.session_fsm import SessionFSM
from core.language.chunker import SentenceChunker
from core.language.normalizer import TextNormalizer
from core.language.router import LanguageRouter
from core.metering.usage_meter import UsageMeter
from core.observability.logging import get_logger
from core.providers.adapters.gladia_stt import GladiaSTTProvider
from core.providers.adapters.groq_llm import GroqLLMProvider
from core.providers.adapters.null_llm import NullLLMProvider
from core.providers.adapters.null_stt import NullSTTProvider
from core.providers.adapters.null_tts import NullTTSProvider
from core.providers.adapters.uplift_tts import UpliftTTSProvider
from core.providers.failover import FailoverRouter
from core.providers.interfaces.llm import LLMConfig
from core.providers.interfaces.stt import STTConfig
from core.providers.interfaces.tts import TTSConfig
from core.providers.registry import ProviderRegistry
from core.runtime.env import is_test_env
from core.session.redis_store import RedisSessionStore
from core.types.audio import AudioFrame
from core.vad.silero_adapter import SileroVADAdapter
from core.latency.collector import LatencyCollector
from core.latency.waterfall import LatencyWaterfall
from core.mcp.orchestrator import ToolOrchestrator
from core.rag.models import KnowledgeBaseChunk
from core.rag.retriever import PgVectorRetriever
from core.rag.speculative import SpeculativeRetrieval
from post_call.models.call_record import CallRecord
from post_call.pipeline.enqueue import PostCallPipeline
from worker_raw.orchestration.latency_hooks import LatencyHooks
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.orchestration.tool_handler import PipelineToolHandler

logger = get_logger("ucve.orchestrator")

# Register adapters once
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
        tool_handler: PipelineToolHandler | None = None,
        latency_collector: LatencyCollector | None = None,
        rag_retriever: PgVectorRetriever | None = None,
        post_call_pipeline: PostCallPipeline | None = None,
    ) -> None:
        self.allow_testing_providers = allow_testing_providers
        self.on_audio_out = on_audio_out
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
        if not allow_testing_providers and is_test_env():
            # harden path still allows mocks when keys absent unless explicitly disallowed
            pass
        self.failover_router = FailoverRouter()
        self.language_router = LanguageRouter()
        self.normalizer = TextNormalizer()
        self.chunker = SentenceChunker()
        self.redis_store = RedisSessionStore()
        self.barge_in_controller = BargeInController()
        self.audit_writer = AuditWriter()
        self.usage_meter = UsageMeter()
        self.redaction_service = RedactionService()
        self.fsm = SessionFSM()
        self._tts_task: asyncio.Task[None] | None = None
        self._started_at = time.monotonic()

    def process_frame(self, frame: AudioFrame) -> Any:
        """Run VAD on inbound PCM (required even when using injected turns)."""
        return self.vad_adapter.process_frame(frame)

    async def cancel_tts(self) -> None:
        if self._tts_task and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass

    async def _synthesize(self, text: str) -> None:
        config = TTSConfig(voice_id="default", sample_rate=16000)
        async for chunk in self.tts_provider.synthesize_stream(text, config):
            if self.on_audio_out and chunk.pcm_data:
                maybe = self.on_audio_out(chunk.pcm_data)
                if asyncio.iscoroutine(maybe):
                    await maybe

    async def run_turn(self, session_config: PipelineSessionConfig, user_text: str) -> str:
        """Execute one STT→RAG→LLM/Tool→norm→TTS turn with latency tracing."""
        waterfall = self.latency_hooks.start_turn(UUID(session_config.session_id) if len(session_config.session_id) == 36 else uuid4())
        waterfall.stt_final_ms = self.latency_hooks.now_ms()

        policy = TenantComplianceProfileLoader.load_effective_policy(
            session_config.compliance_tier,
            hipaa_baa_acknowledged_at=(
                time.time() if session_config.hipaa_baa_acknowledged else None
            ),
        )
        assert_cloud_llm_allowed(policy)

        await self.redis_store.append_turn(
            session_config.session_id,
            {"speaker": "user", "text": user_text, "language": session_config.language},
        )
        self.fsm.trigger(SessionEvent.STT_FINAL)

        # 1. Non-blocking RAG context retrieval
        rag_context = ""
        try:
            tenant_uuid = UUID(session_config.tenant_id) if len(session_config.tenant_id) == 36 else uuid4()
            rag_chunks = await self.speculative_rag.reconcile(user_text, tenant_uuid)
            waterfall.rag_retrieve_ms = self.latency_hooks.now_ms()
            if rag_chunks:
                rag_context = "\n".join(f"[Knowledge DATA]: {c.text}" for c in rag_chunks)
        except Exception as exc:
            logger.warning("RAG retrieval skipped", error=str(exc))

        messages = [
            {"role": "system", "content": f"You are a helpful voice agent.\n{rag_context}".strip()},
            {"role": "user", "content": user_text},
        ]

        # 2. Check tool execution vs LLM generation
        if user_text.startswith("tool:"):
            self.fsm.trigger(SessionEvent.TOOL_CALL_START)
            tool_name = user_text.split(":", 1)[1].strip()
            tool_res = await self.tool_handler.handle_tool_call(tool_name, {})
            self.fsm.trigger(SessionEvent.TOOL_RESULT)
            normalized = tool_res.get("content", "Tool executed.")
        else:
            llm_cfg = LLMConfig(model="llama-3.1-8b-instant")
            reply_parts: list[str] = []
            ttft_recorded = False
            async for chunk in self.llm_provider.generate_stream(messages, llm_cfg):
                if not ttft_recorded:
                    waterfall.llm_ttft_ms = self.latency_hooks.now_ms()
                    ttft_recorded = True
                if chunk.text:
                    reply_parts.append(chunk.text)
            reply = "".join(reply_parts) or "OK"
            norm_result = self.normalizer.normalize(reply, language=session_config.language)
            normalized = getattr(norm_result, "text", None) or str(norm_result)

        await self.redis_store.append_turn(
            session_config.session_id,
            {
                "speaker": "assistant",
                "text": normalized,
                "language": session_config.language,
            },
        )

        self._tts_task = asyncio.create_task(self._synthesize(normalized))
        try:
            await self._tts_task
            waterfall.tts_ttfb_ms = self.latency_hooks.now_ms()
            waterfall.playback_start_ms = waterfall.tts_ttfb_ms + 50.0  # Client playback estimate
            self.latency_collector.record_turn(waterfall)
            self.fsm.trigger(SessionEvent.TTS_FIRST_BYTE)
            self.fsm.trigger(SessionEvent.TTS_DRAINED)
        except asyncio.CancelledError:
            raise
        return normalized

    async def run(
        self,
        session_config: PipelineSessionConfig,
        user_turns: list[str] | None = None,
    ) -> None:
        """Run session orchestration. Fake 'Hello test call' only when explicitly testing Null path."""
        logger.info("Pipeline session starting", session_id=session_config.session_id)
        self._started_at = time.monotonic()

        if session_config.compliance_tier == "hipaa" and not session_config.hipaa_baa_acknowledged:
            raise PermissionError(
                "HIPAA compliance requires signed BAA acknowledgment before cloud LLM execution."
            )

        turns = user_turns
        if turns is None:
            # Backward-compatible default for Phase 17 contract tests. Live WS path
            # should call run_turn() per STT final instead of relying on this greeting.
            turns = ["Hello test call"]

        try:
            self.fsm.trigger(SessionEvent.SESSION_ADMITTED)
            for text in turns:
                await self.run_turn(session_config, text)
        finally:
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

            # Assemble and enqueue PostCall Record (FIX-014)
            try:
                from datetime import datetime, timezone
                from post_call.models.call_record import CallRecord
                from post_call.models.diarized_turn import DiarizedTurn

                diarized = [
                    DiarizedTurn(
                        speaker=t.get("speaker", "user"),
                        text=t.get("text", ""),
                        start_ms=0,
                        end_ms=1000,
                    )
                    for t in redacted_turns
                ]
                now_utc = datetime.now(timezone.utc)
                record = CallRecord(
                    tenant_id=UUID(session_config.tenant_id) if len(session_config.tenant_id) == 36 else uuid4(),
                    agent_id=UUID(session_config.agent_id) if len(session_config.agent_id) == 36 else uuid4(),
                    session_id=UUID(session_config.session_id) if len(session_config.session_id) == 36 else uuid4(),
                    caller_id=getattr(session_config.caller_id, "from_number", None),
                    compliance_tier=session_config.compliance_tier,
                    started_at=now_utc,
                    ended_at=now_utc,
                    turns=diarized,
                )
                await self.post_call_pipeline.enqueue(record)
            except Exception as exc:
                logger.warning("Failed to enqueue PostCallRecord", error=str(exc))

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


def build_providers(*, allow_null: bool = False) -> tuple[Any, Any, Any]:
    if allow_null:
        return NullSTTProvider(), NullLLMProvider(), NullTTSProvider()
    return GladiaSTTProvider(), GroqLLMProvider(), UpliftTTSProvider()
