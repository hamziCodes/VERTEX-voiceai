from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from core.db.repos.post_call_repo import InMemoryPostCallRepository
from core.metering.usage_meter import UsageMeter
from core.providers.interfaces.vad import VADEvent
from core.runtime.admission import SessionAdmissionController
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
    decoded_media_payloads,
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


@pytest.mark.asyncio
async def test_fake_carrier_audio_crosses_complete_voice_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    session_id, tenant_id, agent_id = uuid4(), uuid4(), uuid4()
    config = authoritative_config(
        session_id=str(session_id), tenant_id=str(tenant_id), agent_id=str(agent_id)
    )
    stack = FakeProviderStack(
        stt=SequenceSTT(["Where is my delivery"]),
        llm=SequenceLLM(["Your delivery arrives today"]),
        tts=SequenceTTS(chunks_per_call=2),
    )
    repo = InMemoryPostCallRepository()
    meter = UsageMeter(force_memory=True)
    orchestrator = PipelineOrchestrator(
        provider_binder=ProviderSessionBinder(stack),
        post_call_pipeline=PostCallPipeline(repo),
    )
    orchestrator.vad_adapter = ScriptedVAD(
        [VADEvent(True, False, 1.0), VADEvent(False, True, 0.0)]
    )  # type: ignore[assignment]
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
    supervisor = TelephonySessionSupervisor(
        adapter=adapter,
        orchestrator=orchestrator,
        config=config,
        caller_id=CallerIdContext(
            from_number="+15551230001",
            to_number="+15551230002",
            sip_call_id=CALL_CONTROL_ID,
        ),
        admission=SessionAdmissionController(max_sessions=2, force_memory=True),
        registry=TelephonySessionRegistry(),
        usage_meter=meter,
    )

    run = asyncio.create_task(
        supervisor.run(signature_header=signature, timestamp_header=timestamp, now=NOW)
    )
    await socket.feed(connected())
    await socket.feed(start())
    await supervisor.wait_ready()
    await socket.feed(media(1))
    await socket.feed(media(2, speech=False))
    await wait_until(lambda: len(sent_events(socket, "media")) >= 1, attempts=500)
    await socket.feed(stop())
    await run

    payloads = decoded_media_payloads(socket)
    assert stack.stt.audio_bytes > 0
    assert stack.llm.calls == 1
    assert stack.tts.chunks_yielded > 0
    assert payloads and all(
        payload and payload != b"\xff" * len(payload) for payload in payloads
    )
    record = await repo.get_call(tenant_id, session_id)
    assert [turn.speaker for turn in record.turns] == ["user", "assistant"]
    assert record.ended_at is not None
    assert len(repo._post_call_jobs) == 1
