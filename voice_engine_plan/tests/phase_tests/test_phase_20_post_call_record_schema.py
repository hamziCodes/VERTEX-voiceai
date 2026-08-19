"""Phase 20: Post-Call Intelligence Core Record Schema."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_20_post_call_intelligence_core_record_schema.md"
    )
    assert plan.is_file()


def test_call_record_model_validates() -> None:
    try:
        from post_call.models.call_record import CallRecord  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 20 implementation pending: {exc}")
    record = CallRecord(
        call_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        agent_id="00000000-0000-0000-0000-000000000003",
        session_id="00000000-0000-0000-0000-000000000004",
        caller_id=None,
        transport_type="websocket",
        compliance_tier="standard",
        turns=[],
    )
    assert record.call_id.endswith("0001")
    assert record.caller_id is None


def test_call_record_accepts_e164_caller_id() -> None:
    try:
        from post_call.models.call_record import CallRecord  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 20 implementation pending: {exc}")
    record = CallRecord(
        call_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        agent_id="00000000-0000-0000-0000-000000000003",
        session_id="00000000-0000-0000-0000-000000000004",
        caller_id="+14155552671",
        transport_type="sip",
        compliance_tier="standard",
        turns=[],
    )
    assert record.caller_id == "+14155552671"
