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
    policy = redaction_module.RedactionPolicy(redact_pii_in_transcript=True)
    turns = [{"speaker": "user", "text": "Call 555-123-4567"}]
    out = RedactionService().redact_transcript(turns, policy)
    assert "555-123-4567" not in out[0]["text"]
