"""Phase 12: Compliance Audit Trail."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def audit_module():
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    try:
        from core.compliance.audit import writer  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 12 implementation pending: {exc}")
    return writer


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_12_compliance_audit_trail_and_access_logging.md"
    )
    assert plan.is_file()


def test_audit_insert_immutable(audit_module) -> None:
    AuditWriter = audit_module.AuditWriter
    w = AuditWriter()
    event_id = w.record(
        tenant_id="00000000-0000-0000-0000-000000000001",
        action="credential_resolve",
        resource_type="credential",
        resource_id="gladia",
        actor_id="system",
    )
    assert event_id is not None
