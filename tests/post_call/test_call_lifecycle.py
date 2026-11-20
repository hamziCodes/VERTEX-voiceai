from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.db.repos.post_call_repo import (
    InMemoryPostCallRepository,
    PostCallConflictError,
    PostCallNotFoundError,
)
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.policy import PostCallPolicy
from post_call.models.recording import CallRecording, RecordingState
from post_call.pipeline.enqueue import PostCallPipeline
from post_call.pipeline.recording_policy import RecordingPolicy
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


def test_privacy_first_policy_defaults_and_bounds() -> None:
    policy = PostCallPolicy()

    assert policy.recording_enabled is False
    assert policy.recording_consent_obtained is False
    assert policy.transcript_retention_days == 30
    assert policy.recording_retention_days == 7
    assert policy.storage_region == "local"
    assert policy.requires_review_for_external_actions is True

    with pytest.raises(ValidationError):
        PostCallPolicy(transcript_retention_days=31)
    with pytest.raises(ValidationError):
        PostCallPolicy(recording_retention_days=8)


def test_recording_available_requires_complete_storage_evidence() -> None:
    with pytest.raises(ValidationError):
        CallRecording(state=RecordingState.AVAILABLE)

    recording = CallRecording(
        state=RecordingState.AVAILABLE,
        recording_s3_uri="objects://pk-isb/tenant/session.wav",
        checksum="a" * 64,
        channel_count=1,
        duration_sec=4.25,
        storage_region="pk-isb",
    )

    assert recording.state is RecordingState.AVAILABLE
    assert recording.dual_channel is False

    with pytest.raises(ValidationError, match="recording_state"):
        CallRecord(
            tenant_id=uuid4(),
            agent_id=uuid4(),
            session_id=uuid4(),
            started_at=datetime.now(UTC),
            recording=recording,
        )


@pytest.mark.asyncio
async def test_call_lifecycle_is_incremental_tenant_scoped_and_idempotent() -> None:
    repo = InMemoryPostCallRepository()
    tenant_id = uuid4()
    other_tenant = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    started_at = datetime(2026, 10, 26, 10, 0, tzinfo=UTC)
    policy = PostCallPolicy(storage_region="pk-isb")

    started = await repo.start_call(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=policy,
        provider_snapshot={"stt": "gladia", "llm": "groq", "tts": "cartesia"},
    )
    duplicate_start = await repo.start_call(
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=policy,
        provider_snapshot={"stt": "gladia", "llm": "groq", "tts": "cartesia"},
    )

    assert duplicate_start.call_id == started.call_id
    assert started.started_at == started_at
    assert started.ended_at is None
    assert started.recording_state is RecordingState.NOT_REQUESTED

    first_turn = DiarizedTurn(
        speaker="user",
        text="I need help with my order.",
        start_ms=120,
        end_ms=920,
        confidence=0.96,
    )
    appended = await repo.append_turn(
        tenant_id=tenant_id,
        session_id=session_id,
        ordinal=0,
        turn=first_turn,
    )
    duplicate_turn = await repo.append_turn(
        tenant_id=tenant_id,
        session_id=session_id,
        ordinal=0,
        turn=first_turn,
    )

    assert appended.turns == [first_turn]
    assert duplicate_turn.turns == [first_turn]
    with pytest.raises(PostCallConflictError):
        await repo.append_turn(
            tenant_id=tenant_id,
            session_id=session_id,
            ordinal=0,
            turn=first_turn.model_copy(update={"text": "different"}),
        )
    with pytest.raises(PostCallNotFoundError):
        await repo.get_call(other_tenant, session_id)

    ended_at = started_at + timedelta(seconds=12)
    finalized = await repo.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=ended_at,
        end_reason="client_disconnect",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={"audible_e2e_ms": 740},
        usage_snapshot={"agent_sec": 12.0},
        recording_state=RecordingState.NOT_REQUESTED,
    )
    duplicate_finalize = await repo.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=ended_at + timedelta(seconds=30),
        end_reason="should_not_overwrite",
        disposition=CallDisposition.UNRESOLVED,
        metrics_snapshot={"audible_e2e_ms": 9999},
        usage_snapshot={"agent_sec": 99.0},
        recording_state=RecordingState.FAILED,
        recording_error_code="late_failure",
    )

    assert finalized.ended_at == ended_at
    assert duplicate_finalize.ended_at == ended_at
    assert duplicate_finalize.end_reason == "client_disconnect"
    assert duplicate_finalize.recording_state is RecordingState.NOT_REQUESTED


@pytest.mark.asyncio
async def test_recording_requires_enablement_and_consent_before_recording_state() -> (
    None
):
    repo = InMemoryPostCallRepository()
    tenant_id = uuid4()
    session_id = uuid4()

    await repo.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=datetime.now(UTC),
        transport_type="sip",
        policy=PostCallPolicy(recording_enabled=True),
        provider_snapshot={},
    )

    with pytest.raises(PostCallConflictError, match="consent"):
        await repo.set_recording_state(
            tenant_id=tenant_id,
            session_id=session_id,
            state=RecordingState.RECORDING,
        )


@pytest.mark.asyncio
async def test_available_recording_round_trips_verified_evidence() -> None:
    repo = InMemoryPostCallRepository()
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC)
    await repo.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="sip",
        policy=PostCallPolicy(
            recording_enabled=True,
            recording_consent_obtained=True,
            storage_region="pk-isb",
        ),
        provider_snapshot={},
    )
    evidence = CallRecording(
        recording_s3_uri="objects://pk-isb/tenant/session.wav",
        checksum="c" * 64,
        channel_count=2,
        dual_channel=True,
        duration_sec=2.5,
        storage_region="pk-isb",
    )

    record = await repo.finalize_call(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=3),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={},
        recording_state=RecordingState.AVAILABLE,
        recording=evidence,
    )

    assert record.recording == evidence
    assert record.recording_state is RecordingState.AVAILABLE


@pytest.mark.asyncio
async def test_recording_evidence_cannot_be_hidden_under_another_state() -> None:
    repo = InMemoryPostCallRepository()
    tenant_id, session_id = uuid4(), uuid4()
    started_at = datetime.now(UTC)
    await repo.start_call(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="sip",
        policy=PostCallPolicy(
            recording_enabled=True,
            recording_consent_obtained=True,
            storage_region="pk-isb",
        ),
        provider_snapshot={},
    )
    evidence = CallRecording(
        recording_s3_uri="objects://pk-isb/tenant/session.wav",
        checksum="e" * 64,
        duration_sec=1.0,
        storage_region="pk-isb",
    )

    with pytest.raises(PostCallConflictError, match="available"):
        await repo.finalize_call(
            tenant_id=tenant_id,
            session_id=session_id,
            ended_at=started_at + timedelta(seconds=2),
            end_reason="complete",
            disposition=CallDisposition.COMPLETED,
            metrics_snapshot={},
            usage_snapshot={},
            recording_state=RecordingState.NOT_REQUESTED,
            recording=evidence,
        )
    with pytest.raises(PostCallConflictError, match="failed"):
        await repo.set_recording_state(
            tenant_id=tenant_id,
            session_id=session_id,
            state=RecordingState.NOT_REQUESTED,
            error_code="hidden_error",
        )


@pytest.mark.asyncio
async def test_pipeline_does_not_guess_hipaa_recording_requirement() -> None:
    repo = InMemoryPostCallRepository()
    pipeline = PostCallPipeline(repo=repo)
    tenant_id = uuid4()
    session_id = uuid4()
    started_at = datetime.now(UTC)

    assert RecordingPolicy.is_recording_required("hipaa") is False
    await pipeline.start_session(
        tenant_id=tenant_id,
        agent_id=uuid4(),
        session_id=session_id,
        started_at=started_at,
        transport_type="websocket",
        policy=PostCallPolicy(storage_region="pk-isb"),
        provider_snapshot={"stt": "gladia"},
        compliance_tier="hipaa",
    )
    await pipeline.append_turn(
        tenant_id=tenant_id,
        session_id=session_id,
        ordinal=0,
        turn=DiarizedTurn(
            speaker="user",
            text="Generated test transcript.",
            start_ms=0,
            end_ms=300,
        ),
    )
    record = await pipeline.finalize_session(
        tenant_id=tenant_id,
        session_id=session_id,
        ended_at=started_at + timedelta(seconds=1),
        end_reason="complete",
        disposition=CallDisposition.COMPLETED,
        metrics_snapshot={},
        usage_snapshot={"agent_sec": 1.0},
        recording_state=RecordingState.NOT_REQUESTED,
    )

    assert record.recording is None
    assert record.recording_state is RecordingState.NOT_REQUESTED
    assert len(record.turns) == 1


@pytest.mark.asyncio
async def test_voice_pipeline_persists_truthful_record_without_fake_recording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    repo = InMemoryPostCallRepository()
    pipeline = PostCallPipeline(repo=repo)
    orchestrator = PipelineOrchestrator(post_call_pipeline=pipeline)
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    config = PipelineSessionConfig(
        session_id=str(session_id),
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
    )

    await orchestrator.run(config, user_turns=["Generated test turn."])
    record = await repo.get_call(tenant_id, session_id)

    assert record.ended_at is not None
    assert record.ended_at >= record.started_at
    assert record.recording_state is RecordingState.NOT_REQUESTED
    assert record.recording is None
    assert [turn.speaker for turn in record.turns] == ["user", "assistant"]
    assert record.provider_snapshot == {
        "stt": "gladia",
        "llm": "groq",
        "tts": "uplift",
    }


@pytest.mark.asyncio
async def test_voice_pipeline_reports_requested_recording_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    repo = InMemoryPostCallRepository()
    orchestrator = PipelineOrchestrator(post_call_pipeline=PostCallPipeline(repo=repo))
    tenant_id, agent_id, session_id = uuid4(), uuid4(), uuid4()
    config = PipelineSessionConfig(
        session_id=str(session_id),
        tenant_id=str(tenant_id),
        agent_id=str(agent_id),
        recording_enabled=True,
        recording_consent_obtained=True,
    )

    await orchestrator.run(config, user_turns=[])
    record = await repo.get_call(tenant_id, session_id)

    assert record.recording_state is RecordingState.FAILED
    assert record.recording_error_code == "recording_capture_unavailable"
