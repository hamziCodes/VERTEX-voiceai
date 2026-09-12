"""H4: compliance fail-closed (BAA override, erasure, purge)."""

from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path

import pytest

from core.compliance.erasure import ErasureOrchestrator
from core.compliance.tenant_profile import (
    TenantComplianceProfileLoader,
    assert_cloud_llm_allowed,
    assert_lawful_basis,
)
from core.compliance.tiers import ComplianceTier


def test_hipaa_without_baa_blocks_cloud_llm() -> None:
    policy = TenantComplianceProfileLoader.load_effective_policy(
        ComplianceTier.HIPAA,
        hipaa_baa_acknowledged_at=None,
        policy_overrides={"allow_cloud_llm": True},
    )
    assert policy.allow_cloud_llm is False
    with pytest.raises(PermissionError):
        assert_cloud_llm_allowed(policy)


def test_override_cannot_disable_encryption_on_hipaa() -> None:
    policy = TenantComplianceProfileLoader.load_effective_policy(
        ComplianceTier.HIPAA,
        hipaa_baa_acknowledged_at=datetime.datetime.now(datetime.timezone.utc),
        policy_overrides={"encryption_required": False},
    )
    assert policy.encryption_required is True


def test_gdpr_lawful_basis_required() -> None:
    policy = TenantComplianceProfileLoader.load_effective_policy(
        ComplianceTier.GDPR_STRICT
    )
    with pytest.raises(PermissionError):
        assert_lawful_basis(policy, {})
    assert_lawful_basis(policy, {"lawful_basis": "consent"})


def test_erasure_deletes_fixture_row() -> None:
    orch = ErasureOrchestrator()
    orch.register_session_fixture("tenant-e", "sess-e")
    assert orch.has_session("sess-e")
    result = orch.execute_tenant_erasure("tenant-e")
    assert result["status"] == "completed"
    assert not orch.has_session("sess-e")


def test_erasure_noop_is_failed() -> None:
    orch = ErasureOrchestrator()
    result = orch.execute_tenant_erasure("tenant-missing")
    assert result["status"] == "failed"


def test_purge_job_deletes_fixture_session(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    path = Path(__file__).resolve().parents[2] / "worker_jobs" / "purge_retention.py"
    if not path.exists():
        path = Path(__file__).resolve().parents[2] / "worker-jobs" / "purge_retention.py"
    spec = importlib.util.spec_from_file_location("purge_retention_h4", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    mod.clear_fixture_sessions()
    past = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
    mod.seed_fixture_session(
        {"session_id": "sess-purge-1", "purge_after": past, "legal_hold": False}
    )
    count = mod.run_purge_job()
    assert count == 1
    assert all(
        (s.get("session_id") or s.get("id")) != "sess-purge-1"
        for s in mod._FIXTURE_SESSIONS
    )
