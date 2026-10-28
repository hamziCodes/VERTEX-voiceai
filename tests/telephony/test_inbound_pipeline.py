from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from core.db.repos.post_call_repo import InMemoryPostCallRepository
from core.metering.kinds import AGENT_SEC, STT_SEC, TELEPHONY_SEC, TTS_SEC
from core.metering.usage_meter import UsageMeter
from core.providers.interfaces.vad import VADEvent
from core.runtime.admission import CapacityExceededError, SessionAdmissionController
from core.transport.caller_id import CallerIdContext
from post_call.pipeline.enqueue import PostCallPipeline
from telephony_gateway.adapters.telnyx_media_stream import TelnyxMediaStreamAdapter
from tests.telephony.fake_inbound import (
    CALL_CONTROL_ID,
    NOW,
    STREAM_URL,
    FakeProviderStack,
    ScriptedVAD,
    SequenceLLM,
    SequenceSTT,
    SequenceTTS,
    authoritative_config,
    connected,
    media,
    sent_events,
    signed_media_headers,
    start,
    stop,
)
from tests.telephony.fake_telnyx import FakeTelnyxSocket, wait_until
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.provider_binding import ProviderSessionBinder
from worker_raw.telephony.session_supervisor import (
    TelephonySessionRegistry,
    TelephonySessionSupervisor,
)


def _build_session(*, vad_events: list[VADEvent], tts_chunks: int = 2):
    session_id, tenant_id, agent_id = uuid4(), uuid4(), uuid4()
    config = authoritative_config(
        session_id=str(session_id), tenant_id=str(tenant_id), agent_id=str(agent_id)
    )
    stack = FakeProviderStack(
        stt=SequenceSTT(["Please check my order", "Actually stop"]),
        llm=SequenceLLM(["Your order is ready", "I stopped"]),
        tts=SequenceTTS(chunks_per_call=tts_chunks),
    )
    repo = InMemoryPostCallRepository()
    meter = UsageMeter(force_memory=True)
    orchestrator = PipelineOrchestrator(
        provider_binder=ProviderSessionBinder(stack),
        post_call_pipeline=PostCallPipeline(repo),
    )
    orchestrator.vad_adapter = ScriptedVAD(vad_events)  # type: ignore[assignment]
    orchestrator._vad_worker = None
    orchestrator._speech_capture = None
    orchestrator._barge_verify = None
    socket = FakeTelnyxSocket()
    public_key, signature, timestamp = signed_media_headers()
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=lambda _frame: None,
    )
    admission = SessionAdmissionController(max_sessions=4, force_memory=True)
    registry = TelephonySessionRegistry()
    supervisor = TelephonySessionSupervisor(
        adapter=adapter,
        orchestrator=orchestrator,
        config=config,
        caller_id=CallerIdContext(
            from_number="+15551230001",
            to_number="+15551230002",
            sip_call_id=CALL_CONTROL_ID,
        ),
        admission=admission,
        registry=registry,
        usage_meter=meter,
        startup_timeout_sec=1.0,
    )
    return locals()


@pytest.mark.asyncio
async def test_full_inbound_turn_and_duplicate_hangup_finalize_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(
        vad_events=[VADEvent(True, False, 1.0), VADEvent(False, True, 0.0)]
    )
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await socket.feed(media(1))
    await socket.feed(media(2, speech=False))
    await wait_until(lambda: len(sent_events(socket, "media")) >= 1, attempts=500)
    await socket.feed(stop())
    await supervisor.stop("duplicate_carrier_stop")
    await run

    stack = ctx["stack"]
    assert stack.stt.calls == stack.llm.calls == 1
    assert stack.stt.audio_bytes > 0 and stack.tts.calls >= 1
    repo, config = ctx["repo"], ctx["config"]
    record = await repo.get_call(UUID(config.tenant_id), UUID(config.session_id))
    assert record.transport_type == "telephony"
    assert record.caller_id == "+15551230001"
    assert record.ended_at is not None and record.usage_snapshot["telephony_sec"] > 0
    assert len(repo._post_call_jobs) == 1
    events = ctx["meter"]._events_log
    assert {event["kind"] for event in events} == {
        AGENT_SEC,
        STT_SEC,
        TTS_SEC,
        TELEPHONY_SEC,
    }
    assert len(events) == 4
    assert ctx["admission"].active_session_count == ctx["registry"].active_count == 0
    assert ctx["adapter"].tasks_alive == ctx["orchestrator"].runtime_task_count == 0


@pytest.mark.asyncio
async def test_barge_in_clears_carrier_audio_and_keeps_interrupting_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(
        vad_events=[
            VADEvent(True, False, 1.0),
            VADEvent(False, True, 0.0),
            VADEvent(True, False, 1.0),
            VADEvent(False, True, 0.0),
        ],
        tts_chunks=8,
    )
    ctx["stack"].tts.block_between = True
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await socket.feed(media(1))
    await socket.feed(media(2, speech=False))
    await wait_until(lambda: len(sent_events(socket, "media")) >= 1, attempts=500)
    await socket.feed(media(3))
    await socket.feed(media(4, speech=False))
    await wait_until(lambda: len(sent_events(socket, "clear")) == 1, attempts=500)
    ctx["stack"].tts.release.set()
    await wait_until(lambda: ctx["stack"].llm.calls >= 2, attempts=500)
    await socket.feed(stop())
    await run

    assert ctx["stack"].stt.calls == 2
    assert ctx["stack"].llm.calls >= 2
    assert ctx["orchestrator"].barge_in_controller.committed_count == 1
    assert len(sent_events(socket, "clear")) == 1
    assert ctx["adapter"].tasks_alive == 0


@pytest.mark.asyncio
async def test_non_authoritative_plan_fails_before_media_or_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    ctx = _build_session(vad_events=[])
    ctx["config"].plan_authoritative = False
    with pytest.raises(ValueError, match="authoritative"):
        await ctx["supervisor"].run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    assert ctx["admission"].active_session_count == ctx["registry"].active_count == 0
    assert ctx["socket"].sent == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("termination", "expected_reason"),
    [
        ("disconnect", "unexpected_media_disconnect"),
        ("worker", "worker_shutdown"),
        ("timeout", "max_duration_reached"),
    ],
)
async def test_termination_paths_finalize_and_release_once(
    monkeypatch: pytest.MonkeyPatch,
    termination: str,
    expected_reason: str,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(vad_events=[])
    if termination == "timeout":
        ctx["config"].max_duration_sec = 0.05
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    if termination == "disconnect":
        await socket.disconnect()
    elif termination == "worker":
        await supervisor.stop("worker_shutdown")
        await supervisor.stop("ignored_duplicate")
    await asyncio.wait_for(run, timeout=2.0)

    config = ctx["config"]
    record = await ctx["repo"].get_call(UUID(config.tenant_id), UUID(config.session_id))
    assert record.end_reason == expected_reason
    assert record.ended_at is not None
    assert len(ctx["repo"]._post_call_jobs) == 1
    assert ctx["admission"].active_session_count == 0
    assert ctx["registry"].active_count == 0
    assert ctx["adapter"].tasks_alive == 0
    assert ctx["orchestrator"].runtime_task_count == 0


@pytest.mark.asyncio
async def test_provider_pipeline_failure_uses_same_finalizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(
        vad_events=[VADEvent(True, False, 1.0), VADEvent(False, True, 0.0)]
    )

    async def fail_turn(_config, _text: str) -> str:
        raise RuntimeError("synthetic provider failure")

    ctx["orchestrator"].run_turn = fail_turn
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await socket.feed(media(1))
    await socket.feed(media(2, speech=False))
    await asyncio.wait_for(run, timeout=2.0)

    config = ctx["config"]
    record = await ctx["repo"].get_call(UUID(config.tenant_id), UUID(config.session_id))
    assert record.end_reason == "provider_pipeline_failure"
    assert record.disposition.value == "unresolved"
    assert len(ctx["repo"]._post_call_jobs) == 1
    assert ctx["admission"].active_session_count == 0
    assert ctx["registry"].active_count == 0


@pytest.mark.asyncio
async def test_tool_requested_end_uses_same_finalizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(vad_events=[])
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await ctx["orchestrator"].request_end(
        summary="Caller request completed", disposition="completed"
    )
    await ctx["orchestrator"]._complete_pending_lifecycle()
    await asyncio.wait_for(run, timeout=2.0)

    config = ctx["config"]
    record = await ctx["repo"].get_call(UUID(config.tenant_id), UUID(config.session_id))
    assert record.end_reason == "agent_end_conversation"
    assert len(ctx["repo"]._post_call_jobs) == 1


@pytest.mark.asyncio
async def test_capacity_rejection_does_not_start_pipeline_or_post_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    ctx = _build_session(vad_events=[])
    admission = SessionAdmissionController(max_sessions=1, force_memory=True)
    await admission.acquire("existing-session", "existing-tenant")
    ctx["supervisor"].admission = admission

    with pytest.raises(CapacityExceededError):
        await ctx["supervisor"].run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )

    assert len(ctx["repo"]._calls) == 0
    assert ctx["registry"].active_count == 0
    assert admission.active_session_count == 1
    assert ctx["socket"].sent == []
    await admission.release("existing-session", "existing-tenant")


@pytest.mark.asyncio
async def test_published_turn_limit_closes_before_extra_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    ctx = _build_session(vad_events=[])
    ctx["config"].max_turns = 1
    supervisor, socket = ctx["supervisor"], ctx["socket"]
    run = asyncio.create_task(
        supervisor.run(
            signature_header=ctx["signature"],
            timestamp_header=ctx["timestamp"],
            now=NOW,
        )
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await supervisor.enqueue_voice_turn("first allowed turn")
    await wait_until(lambda: ctx["stack"].llm.calls == 1, attempts=500)
    await supervisor.enqueue_voice_turn("second rejected turn")
    await asyncio.wait_for(run, timeout=2.0)

    config = ctx["config"]
    record = await ctx["repo"].get_call(UUID(config.tenant_id), UUID(config.session_id))
    assert record.end_reason == "max_turns_reached"
    assert ctx["stack"].llm.calls == 1
