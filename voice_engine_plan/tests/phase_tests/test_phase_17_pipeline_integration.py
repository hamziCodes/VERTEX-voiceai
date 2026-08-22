"""Phase 17: Real-Time Orchestration Pipeline Integration."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_17_real_time_orchestration_pipeline_integration.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_pipeline_orchestrator_exists() -> None:
    from worker_raw.orchestration.pipeline import PipelineOrchestrator
    orchestrator = PipelineOrchestrator()
    assert orchestrator is not None


@pytest.mark.asyncio
async def test_ws_connect_and_jwt_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    from control_plane.auth.jwt import issue_session_jwt
    from core.transport.native_websocket import NativeWebSocketTransport

    token = issue_session_jwt("t1", "s1", "a1")
    transport = NativeWebSocketTransport()

    # Valid token succeeds
    success = await transport.connect("conn-1", token)
    assert success is True
    assert transport.is_connected is True

    # Invalid token fails
    transport_bad = NativeWebSocketTransport()
    fail = await transport_bad.connect("conn-2", "invalid-token")
    assert fail is False
    assert transport_bad.is_connected is False


@pytest.mark.asyncio
async def test_vad_adapter_speech_detection() -> None:
    from core.types.audio import AudioFrame
    from core.vad.silero_adapter import SileroVADAdapter

    vad = SileroVADAdapter()

    # Silent frame (all zeros) -> is_speech = False
    silent_bytes = bytes(640)  # 20ms of 16kHz 16-bit PCM silence
    silent_frame = AudioFrame(pcm16=silent_bytes, sample_rate=16000)
    res_silent = vad.process_frame(silent_frame)
    assert res_silent.speech_start is False

    # Loud speech-like PCM frame -> speech_start = True
    loud_bytes = bytearray()
    for i in range(320):
        val = 15000 if i % 2 == 0 else -15000
        loud_bytes.extend(val.to_bytes(2, byteorder="little", signed=True))

    speech_frame = AudioFrame(pcm16=bytes(loud_bytes), sample_rate=16000)
    res_speech = vad.process_frame(speech_frame)
    assert res_speech.speech_start is True



@pytest.mark.asyncio
async def test_full_talking_session_execution() -> None:
    from worker_raw.orchestration.pipeline import PipelineOrchestrator
    from worker_raw.orchestration.session_config import PipelineSessionConfig

    orchestrator = PipelineOrchestrator()
    config = PipelineSessionConfig(
        session_id="session-e2e-123",
        tenant_id="tenant-e2e-456",
        agent_id="agent-007",
        language="en",
        compliance_tier="standard",
    )

    await orchestrator.run(config)
    assert orchestrator.fsm.state.value == "DISCONNECTED"

    # Verify turn history written to Redis store
    turns = await orchestrator.redis_store.get_turns("session-e2e-123")
    assert len(turns) >= 1
    assert turns[0]["speaker"] == "user"


@pytest.mark.asyncio
async def test_hipaa_gate_blocks_llm_without_baa_ack() -> None:
    from worker_raw.orchestration.pipeline import PipelineOrchestrator
    from worker_raw.orchestration.session_config import PipelineSessionConfig

    orchestrator = PipelineOrchestrator()
    config_hipaa_no_baa = PipelineSessionConfig(
        session_id="session-hipaa-fail",
        tenant_id="tenant-hipaa-1",
        agent_id="agent-hipaa",
        compliance_tier="hipaa",
        hipaa_baa_acknowledged=False,
    )

    with pytest.raises(PermissionError) as exc_info:
        await orchestrator.run(config_hipaa_no_baa)
    assert "HIPAA compliance requires signed BAA" in str(exc_info.value)


@pytest.mark.asyncio
async def test_disconnect_triggers_redaction_and_audit() -> None:
    from worker_raw.orchestration.pipeline import PipelineOrchestrator
    from worker_raw.orchestration.session_config import PipelineSessionConfig

    orchestrator = PipelineOrchestrator()
    audit_events = []

    def audit_cb(evt):
        audit_events.append(evt)

    from core.compliance.audit import on_audit_event
    on_audit_event(audit_cb)

    config = PipelineSessionConfig(
        session_id="session-audit-123",
        tenant_id="tenant-audit-456",
        agent_id="agent-007",
    )

    await orchestrator.run(config)
    assert len(audit_events) >= 1
    latest = audit_events[-1]
    assert latest.action == "call_record_created" or latest.action.value == "call_record_created"


@pytest.mark.asyncio
async def test_reconnect_creates_new_session() -> None:
    from worker_raw.handlers.session_lifecycle import SessionLifecycleHandler
    from worker_raw.orchestration.session_config import PipelineSessionConfig

    handler = SessionLifecycleHandler()
    cfg1 = PipelineSessionConfig(session_id="sess-1", tenant_id="t1", agent_id="a1")
    cfg2 = PipelineSessionConfig(session_id="sess-2", tenant_id="t1", agent_id="a1")

    p1 = await handler.handle_connect(cfg1)
    p2 = await handler.handle_connect(cfg2)

    assert p1 is not p2  # New reconnect creates distinct session orchestrator

