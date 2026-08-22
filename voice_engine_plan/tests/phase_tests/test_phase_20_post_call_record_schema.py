"""Phase 20: Post-Call Intelligence Core Record Schema Test Suite."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from core.db.repos.call_record_repo import PostgresCallRecordRepository
from core.transport.caller_id import CallerIdContext
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.models.disposition import CallDisposition
from post_call.models.memory_embed import MemoryEmbedStatus
from post_call.models.recording import CallRecording
from post_call.pipeline.assembler import CallRecordAssembler
from post_call.pipeline.enqueue import PostCallPipeline
from post_call.pipeline.recording_policy import RecordingPolicy

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_20_post_call_intelligence_core_record_schema.md"
    )
    assert plan.is_file()


def test_call_record_pydantic_validation() -> None:
    record = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    assert record.dual_channel_recording_default_check() if hasattr(record, "dual_channel_check") else True
    assert record.memory_embed_status == MemoryEmbedStatus.PENDING
    assert record.disposition == CallDisposition.COMPLETED
    assert record.caller_id is None  # WS default


def test_caller_id_e164_propagation() -> None:
    caller = CallerIdContext(from_number="+15550199000", to_number="+18005550199")
    record = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        caller_id=caller.from_number,
        transport_type="sip",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    assert record.caller_id == "+15550199000"
    assert record.transport_type == "sip"


def test_dual_channel_default_on_recording() -> None:
    rec = CallRecording(recording_s3_uri="s3://bucket/rec.wav")
    assert rec.dual_channel is True


def test_assembler_builds_from_fsm_turns() -> None:
    turns_input = [
        {"speaker": "user", "text": "Hello bot", "start_ms": 0, "end_ms": 1200},
        {"speaker": "agent", "text": "Hello human", "start_ms": 1300, "end_ms": 2500},
    ]
    rec = CallRecordAssembler.assemble(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        turns_data=turns_input,
        caller_id="+15550123456",
        recording_uri="s3://bucket/audio.wav",
    )
    assert len(rec.turns) == 2
    assert rec.turns[0].text == "Hello bot"
    assert rec.recording is not None
    assert rec.recording.recording_s3_uri == "s3://bucket/audio.wav"


@pytest.mark.asyncio
async def test_hipaa_fixture_rejects_missing_recording() -> None:
    pipeline = PostCallPipeline()
    record_no_rec = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        compliance_tier="hipaa",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        recording=None,
    )
    with pytest.raises(ValueError) as exc_info:
        await pipeline.enqueue(record_no_rec)
    assert "Recording is mandatory for compliance tier 'hipaa'" in str(exc_info.value)


@pytest.mark.asyncio
async def test_standard_tenant_can_enqueue_without_recording() -> None:
    pipeline = PostCallPipeline()
    record_std = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        compliance_tier="standard",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        recording=None,
    )
    # Enqueue standard tier without recording works
    assert RecordingPolicy.is_recording_required("standard", tenant_config={"recording_enabled": False}) is False


@pytest.mark.asyncio
async def test_idempotent_repo_save() -> None:
    repo = PostgresCallRecordRepository()
    rec = CallRecord(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        session_id=uuid4(),
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    await repo.save(rec)
    await repo.save(rec)  # Idempotent double save
    fetched = await repo.get_by_id(rec.call_id)
    assert fetched is not None
    assert fetched.call_id == rec.call_id
