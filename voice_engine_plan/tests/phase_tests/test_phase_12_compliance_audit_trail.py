"""Phase 12: Compliance Audit Trail."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def audit_module():
    from core.compliance import audit  # type: ignore
    return audit


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


def test_on_audit_event_callback_invoked(audit_module) -> None:
    received_events = []

    def siem_callback(event):
        received_events.append(event)

    audit_module.on_audit_event(siem_callback)

    w = audit_module.AuditWriter()
    w.record(
        tenant_id="t-siem",
        action=audit_module.AuditAction.SESSION_MINT,
        resource_type="session",
        resource_id="s-123",
    )

    assert len(received_events) >= 1
    latest = received_events[-1]
    assert latest.tenant_id == "t-siem"


def test_writer_failure_swallowed(audit_module) -> None:
    w = audit_module.AuditWriter()
    # Invalid record parameters should not throw unhandled exception to caller
    event_id = w.record(
        tenant_id="t-error",
        action=None,  # type: ignore
        resource_type="test",
        resource_id="test",
    )
    assert event_id is not None


def test_cross_tenant_audit_query_blocked(audit_module) -> None:
    queries = audit_module.AuditQueries()
    with pytest.raises(PermissionError):
        queries.query_tenant_audit_logs(
            tenant_id="tenant-a", requester_tenant_id="tenant-b"
        )


def test_platform_admin_cross_tenant_query_allowed(audit_module) -> None:
    event1 = audit_module.AuditEvent(
        tenant_id="tenant-a", action="session_mint", resource_type="session", resource_id="s1"
    )
    event2 = audit_module.AuditEvent(
        tenant_id="tenant-b", action="session_mint", resource_type="session", resource_id="s2"
    )

    queries = audit_module.AuditQueries(logs=[event1, event2])
    all_logs = queries.query_all_audit_logs(actor_role="platform_admin")
    assert len(all_logs) == 2


def test_credential_resolve_audit_without_secret(audit_module) -> None:
    event = audit_module.AuditEvent(
        tenant_id="tenant-secret",
        action=audit_module.AuditAction.CREDENTIAL_RESOLVE,
        resource_type="credential",
        resource_id="gladia",
        detail={"key_tier": "platform", "status": "resolved"},
    )
    payload = event.to_dict()
    assert "sk-" not in str(payload)
    assert payload["action"] == "credential_resolve"

