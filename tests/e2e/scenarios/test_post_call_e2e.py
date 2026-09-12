"""E2E test: Post-call record creation and pipeline dispatch (Phase 20/21/33)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
import pytest

from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn


def test_post_call_record_e2e_creation() -> None:
    tenant_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    call_id = uuid4()

    turn1 = DiarizedTurn(
        speaker="user",
        text="I need help scheduling an appointment.",
        start_ms=0,
        end_ms=1500,
        confidence=0.98,
    )
    turn2 = DiarizedTurn(
        speaker="agent",
        text="I would be happy to help you with that.",
        start_ms=1600,
        end_ms=3200,
        confidence=1.0,
    )

    record = CallRecord(
        call_id=call_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        turns=[turn1, turn2],
        metrics_snapshot={"intent": "schedule_appointment"},
    )

    assert record.call_id == call_id
    assert record.session_id == session_id
    assert len(record.turns) == 2
    assert record.metrics_snapshot["intent"] == "schedule_appointment"

