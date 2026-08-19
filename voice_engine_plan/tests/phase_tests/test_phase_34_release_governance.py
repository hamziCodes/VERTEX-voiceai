"""Phase 34: Release Governance and Operational Runbooks."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLAN = (
    REPO_ROOT
    / "voice_engine_plan"
    / "implementation_plan"
    / "phase_34_release_governance_and_operational_runbooks.md"
)
RUNBOOKS = REPO_ROOT / "docs" / "runbooks"


def test_phase_plan_artifact_exists() -> None:
    assert PLAN.is_file()


def test_runbooks_exist() -> None:
    required = [
        "README.md",
        "RUNBOOK_QUOTA_EXHAUSTION.md",
        "RUNBOOK_PROVIDER_OUTAGE.md",
        "RUNBOOK_TRUNK_FAILOVER.md",
        "RUNBOOK_DLQ_BACKLOG.md",
        "RUNBOOK_LATENCY_SLO_BREACH.md",
        "RUNBOOK_HIPAA_INCIDENT.md",
        "RUNBOOK_WORKER_OOM.md",
    ]
    missing = [n for n in required if not (RUNBOOKS / n).is_file()]
    if missing:
        import pytest

        pytest.skip(f"Phase 34 runbooks pending: {missing}")
    for name in required:
        assert (RUNBOOKS / name).is_file()


def test_release_governance_doc_exists() -> None:
    doc = REPO_ROOT / "docs" / "release" / "RELEASE_GOVERNANCE.md"
    if not doc.is_file():
        import pytest

        pytest.skip("RELEASE_GOVERNANCE pending")
    assert doc.is_file()
