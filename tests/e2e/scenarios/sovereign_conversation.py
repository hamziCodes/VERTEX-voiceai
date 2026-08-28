"""Sovereign conversation scenario — in-process mock provider stack (R0).

Flow:
  session admit → text turn → mock LLM stream → TTS chunks →
  barge-in mid-TTS → cancel assertions → second turn → teardown → post-call enqueue
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.fsm.events import SessionEvent
from core.fsm.states import SessionState
from core.providers.interfaces.tts import TTSChunk, TTSConfig
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.recording import CallRecording
from post_call.pipeline.enqueue import PostCallPipeline
from tests.e2e.harness import HarnessConfig, ScenarioResult, register_scenario
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class _SlowChunkTTS:
    """Mock TTS that yields chunks with delay so barge-in can cancel mid-stream."""

    def __init__(self, chunk_delay_s: float = 0.05, n_chunks: int = 8) -> None:
        self.chunk_delay_s = chunk_delay_s
        self.n_chunks = n_chunks
        self.chunks_yielded = 0

    def health_check(self) -> bool:
        return True

    async def synthesize_stream(
        self,
        text: str,
        config: TTSConfig,
        cancellation_token: Any = None,
    ) -> AsyncIterator[TTSChunk]:
        for i in range(self.n_chunks):
            if cancellation_token is not None and getattr(
                cancellation_token, "is_cancelled", False
            ):
                return
            await asyncio.sleep(self.chunk_delay_s)
            self.chunks_yielded += 1
            yield TTSChunk(
                pcm_data=b"\x00\x00" * 160,
                native_sample_rate=config.sample_rate,
                is_final=(i == self.n_chunks - 1),
            )


class _FastTTS:
    def health_check(self) -> bool:
        return True

    async def synthesize_stream(
        self, text: str, config: TTSConfig, cancellation_token: Any = None
    ) -> AsyncIterator[TTSChunk]:
        yield TTSChunk(
            pcm_data=b"\x00\x00" * 80,
            native_sample_rate=config.sample_rate,
            is_final=True,
        )


@register_scenario("sovereign_conversation")
async def run_sovereign_conversation(config: HarnessConfig) -> ScenarioResult:
    """Execute the sovereign conversation path against mock providers."""
    failures: list[str] = []
    metrics: dict[str, Any] = {}
    audio_out: list[bytes] = []
    transcripts: list[tuple[str, str]] = []
    post_call = PostCallPipeline()
    slow_tts = _SlowChunkTTS(chunk_delay_s=0.04, n_chunks=10)

    orch = PipelineOrchestrator(
        on_audio_out=lambda b: audio_out.append(b),
        on_transcript=lambda speaker, text: transcripts.append((speaker, text)),
        post_call_pipeline=post_call,
    )
    orch.tts_provider = slow_tts  # type: ignore[assignment]

    session = PipelineSessionConfig(
        session_id="e2e-sovereign-session",
        tenant_id="e2e-tenant",
        agent_id="e2e-agent",
        language="en",
        compliance_tier="standard",
    )

    # --- Admit ---
    orch.fsm.trigger(SessionEvent.SESSION_ADMITTED)
    metrics["state_after_admit"] = orch.fsm.state.value
    if orch.fsm.state != SessionState.LISTENING:
        failures.append(f"admit: expected LISTENING, got {orch.fsm.state.value}")

    # --- Turn 1: start TTS, barge-in mid-stream ---
    turn1_task = asyncio.create_task(orch.run_turn(session, "hello sovereign"))
    for _ in range(100):
        if slow_tts.chunks_yielded >= 1 or audio_out:
            break
        await asyncio.sleep(0.01)
    else:
        failures.append("turn1: no TTS chunk before barge-in window")

    await orch.cancel_tts()
    try:
        await asyncio.wait_for(turn1_task, timeout=2.0)
    except TimeoutError:
        failures.append("turn1: timed out after barge-in cancel")
        turn1_task.cancel()
        try:
            await turn1_task
        except (asyncio.CancelledError, Exception):
            pass
    except asyncio.CancelledError:
        pass

    if turn1_task.done():
        if turn1_task.cancelled():
            metrics["turn1_outcome"] = "cancelled"
        else:
            exc = turn1_task.exception()
            if exc is None:
                metrics["turn1_outcome"] = "completed"
            elif isinstance(exc, asyncio.CancelledError):
                metrics["turn1_outcome"] = "cancelled_error"
            else:
                failures.append(f"turn1: unexpected error {exc!r}")
                metrics["turn1_outcome"] = type(exc).__name__

    metrics["tts_chunks_before_or_at_cancel"] = slow_tts.chunks_yielded
    metrics["audio_chunks_turn1"] = len(audio_out)
    if orch._tts_task is not None and not orch._tts_task.done():
        failures.append("barge-in: TTS task still running after cancel_tts()")

    # --- Turn 2: complete normally with fast TTS ---
    audio_before = len(audio_out)
    orch.tts_provider = _FastTTS()  # type: ignore[assignment]

    # After mid-TTS cancel, FSM may sit in PROCESSING_INFERENCE (TTS_FIRST_BYTE never fired).
    # run_turn recovers AGENT_SPEAKING via TTS_DRAINED; for PROCESSING_INFERENCE leave as-is.
    if orch.fsm.state == SessionState.AGENT_SPEAKING and orch.fsm.can_transition(
        SessionEvent.TTS_DRAINED
    ):
        orch.fsm.trigger(SessionEvent.TTS_DRAINED)

    try:
        reply2 = await orch.run_turn(session, "second turn please")
        metrics["turn2_reply_len"] = len(reply2 or "")
    except Exception as exc:
        failures.append(f"turn2: {exc!r}")

    if len(audio_out) <= audio_before:
        failures.append("turn2: expected additional TTS audio chunks")

    # --- Teardown + post-call enqueue (mirrors run() finally; WS path lacks this until R2) ---
    try:
        if orch.fsm.can_transition(SessionEvent.DISCONNECT):
            orch.fsm.trigger(SessionEvent.DISCONNECT)
        raw_turns = await orch.redis_store.get_turns(session.session_id)
        diarized = [
            DiarizedTurn(
                speaker=t.get("speaker", "user"),
                text=t.get("text", ""),
                start_ms=0,
                end_ms=1000,
            )
            for t in raw_turns
        ]
        now_utc = datetime.now(timezone.utc)
        record = CallRecord(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            compliance_tier=session.compliance_tier,
            started_at=now_utc,
            ended_at=now_utc,
            turns=diarized,
            recording=CallRecording(
                recording_s3_uri="s3://ucve-test/e2e-sovereign.wav",
                dual_channel=True,
                duration_sec=1.0,
            ),
        )
        await post_call.enqueue(record)
    except Exception as exc:
        failures.append(f"teardown/post-call: {exc!r}")

    metrics["post_call_enqueued"] = len(post_call.processed_records)
    metrics["transcript_events"] = len(transcripts)
    metrics["final_state"] = orch.fsm.state.value

    if metrics["post_call_enqueued"] < 1:
        failures.append("post-call: expected at least one enqueued CallRecord")
    if orch.fsm.state != SessionState.DISCONNECTED:
        failures.append(f"teardown: expected DISCONNECTED, got {orch.fsm.state.value}")

    if config.extra.get("scenario_force_fail"):
        failures.append("forced scenario failure via config.extra")

    if failures:
        return ScenarioResult.fail(*failures, **metrics)
    return ScenarioResult.ok(**metrics)
