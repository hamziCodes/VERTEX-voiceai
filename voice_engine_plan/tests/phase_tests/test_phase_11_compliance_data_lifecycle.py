"""Phase 11: Compliance Data Lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def redaction_module():
    try:
        from core.compliance import redaction  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 11 implementation pending: {exc}")
    return redaction


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_11_compliance_data_lifecycle_retention_deletion_redaction.md"
    )
    assert plan.is_file()


def test_phone_redacted_from_transcript(redaction_module) -> None:
    RedactionService = redaction_module.RedactionService
    RedactionPolicy = redaction_module.RedactionPolicy
    policy = RedactionPolicy(redact_pii_in_transcript=True)
    turns = [{"speaker": "user", "text": "Call 555-123-4567 please"}]
    out = RedactionService().redact_transcript(turns, policy)
    assert "555-123-4567" not in out[0]["text"]


def test_legal_hold_blocks_retention_purge() -> None:
    from core.compliance.legal_hold import LegalHoldManager
    from core.compliance.retention import RetentionScheduler

    hold_mgr = LegalHoldManager()
    hold_mgr.set_legal_hold("session-hold-123", hold=True)

    scheduler = RetentionScheduler(legal_hold_mgr=hold_mgr)
    sessions = [{"session_id": "session-hold-123"}, {"session_id": "session-normal-456"}]

    purged_count = scheduler.purge_expired_sessions(sessions)
    assert purged_count == 1  # session-hold-123 was blocked from purge


def test_gdpr_erasure_cascade() -> None:
    from core.compliance.erasure import ErasureOrchestrator

    orchestrator = ErasureOrchestrator()
    orchestrator.register_session_fixture("tenant-gdpr-123", "sess-gdpr-1")
    record = orchestrator.execute_tenant_erasure("tenant-gdpr-123")
    assert record["status"] == "completed"
    assert "sessions" in record["cascaded_artifacts"]
    assert not orchestrator.has_session("sess-gdpr-1")


def test_retention_days_calculation() -> None:
    import datetime
    from core.compliance.retention import RetentionScheduler

    scheduler = RetentionScheduler()
    started = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    purge_after = scheduler.calculate_purge_after(started, retention_days=30)
    assert purge_after == datetime.datetime(2026, 1, 31, 12, 0, 0, tzinfo=datetime.timezone.utc)

