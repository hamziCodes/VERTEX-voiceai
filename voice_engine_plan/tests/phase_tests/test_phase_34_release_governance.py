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
    for name in required:
        assert (RUNBOOKS / name).is_file(), f"Missing runbook {name}"


def test_readme_indexes_runbooks() -> None:
    readme_text = (RUNBOOKS / "README.md").read_text(encoding="utf-8")
    runbooks = [
        "RUNBOOK_QUOTA_EXHAUSTION.md",
        "RUNBOOK_PROVIDER_OUTAGE.md",
        "RUNBOOK_TRUNK_FAILOVER.md",
        "RUNBOOK_DLQ_BACKLOG.md",
        "RUNBOOK_LATENCY_SLO_BREACH.md",
        "RUNBOOK_HIPAA_INCIDENT.md",
        "RUNBOOK_WORKER_OOM.md",
    ]
    for r in runbooks:
        assert r in readme_text, f"Runbooks README missing link to {r}"


def test_release_governance_doc_exists_and_references_matrix() -> None:
    doc = REPO_ROOT / "docs" / "release" / "RELEASE_GOVERNANCE.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "TEST_MATRIX.md" in text or "test_matrix" in text.lower()


def test_rollback_documents_config_pin_behavior() -> None:
    doc = REPO_ROOT / "docs" / "release" / "ROLLBACK.md"
    assert doc.is_file()
    text = doc.read_text(encoding="utf-8")
    assert "pin" in text.lower()
    assert "active sessions" in text.lower() or "in-flight" in text.lower()


def test_changelog_exists() -> None:
    changelog = REPO_ROOT / "CHANGELOG.md"
    assert changelog.is_file()
    text = changelog.read_text(encoding="utf-8")
    assert "# Changelog" in text


def test_deploy_workflow_stubs_exist() -> None:
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    assert (workflows_dir / "deploy-staging.yml").is_file()
    assert (workflows_dir / "deploy-prod.yml").is_file()


def test_quota_runbook_references_thresholds() -> None:
    quota_rb = (RUNBOOKS / "RUNBOOK_QUOTA_EXHAUSTION.md").read_text(encoding="utf-8")
    assert "80%" in quota_rb
    assert "100%" in quota_rb

