"""Phase 09: Tenant Credential Vaulting."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def vault_module():
    if not os.getenv("UCVE_MASTER_KEY"):
        pytest.skip("UCVE_MASTER_KEY not set")
    try:
        from core.secrets import vault  # type: ignore
    except ImportError as exc:
        pytest.skip(f"Phase 09 implementation pending: {exc}")
    return vault


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_09_tenant_credential_vaulting_and_secret_access_patterns.md"
    )
    assert plan.is_file()


def test_store_resolve_round_trip(vault_module) -> None:
    SecretVault = vault_module.SecretVault
    v = SecretVault()
    v.store(tenant_id="t1", provider_id="gladia", secret="sk-test")
    assert v.resolve(tenant_id="t1", provider_id="gladia") == "sk-test"


def test_missing_secret_fail_closed(vault_module) -> None:
    SecretNotFoundError = vault_module.SecretNotFoundError
    SecretVault = vault_module.SecretVault
    v = SecretVault()
    with pytest.raises(SecretNotFoundError):
        v.resolve(tenant_id="missing", provider_id="gladia")
