"""Phase 09: Tenant Credential Vaulting."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def vault_module():
    from core import secrets  # type: ignore
    return secrets


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
        v.resolve(tenant_id="missing", provider_id="custom_provider", key_tier="byok")


def test_wrong_master_key_fails_decrypt(vault_module) -> None:
    from core.secrets.kms.local_dev import LocalDevKMSBackend
    from core.secrets.vault import SecretVault

    v1 = SecretVault(kms_backend=LocalDevKMSBackend(master_key="key-alpha"))
    v1.store(tenant_id="t1", provider_id="deepgram", secret="sk-secret-123")
    blob, ver = v1._in_memory_db["t1:deepgram:api_key"]

    v2 = SecretVault(kms_backend=LocalDevKMSBackend(master_key="key-beta"))
    v2._in_memory_db["t1:deepgram:api_key"] = (blob, ver)

    DecryptionError = vault_module.DecryptionError
    with pytest.raises(DecryptionError):
        v2.resolve(tenant_id="t1", provider_id="deepgram")


def test_rotate_invalidates_cache(vault_module) -> None:
    SecretVault = vault_module.SecretVault
    v = SecretVault()

    v.store(tenant_id="t1", provider_id="gladia", secret="sk-old")
    assert v.resolve(tenant_id="t1", provider_id="gladia") == "sk-old"

    v.rotate(tenant_id="t1", provider_id="gladia", new_secret="sk-new")
    assert v.resolve(tenant_id="t1", provider_id="gladia") == "sk-new"


def test_hmac_secret_hash_and_verification(vault_module) -> None:
    HMACSecretManager = vault_module.HMACSecretManager

    secret = "my-tenant-hmac-secret-123"
    hashed = HMACSecretManager.hash_secret(secret)
    assert len(hashed) == 64
    assert HMACSecretManager.verify_secret(secret, hashed) is True
    assert HMACSecretManager.verify_secret("wrong-secret", hashed) is False


def test_audit_hook_called_on_resolve(vault_module) -> None:
    SecretVault = vault_module.SecretVault
    v = SecretVault()
    v.store(tenant_id="t-audit", provider_id="groq", secret="sk-groq-key")

    audit_calls = []

    def audit_callback(tenant_id, provider_id, action):
        audit_calls.append((tenant_id, provider_id, action))

    v.register_audit_hook(audit_callback)

    secret = v.resolve(tenant_id="t-audit", provider_id="groq")
    assert secret == "sk-groq-key"
    assert len(audit_calls) == 1
    assert audit_calls[0] == ("t-audit", "groq", "resolve_cached") or audit_calls[0] == ("t-audit", "groq", "resolve_decrypted")


def test_platform_key_fallback(vault_module, monkeypatch) -> None:
    SecretVault = vault_module.SecretVault
    monkeypatch.setenv("PLATFORM_GLADIA_API_KEY", "sk-platform-gladia-from-env")
    v = SecretVault()
    # No tenant BYOK key set, key_tier="platform" -> falls back to env platform key
    platform_key = v.resolve(tenant_id="t-smb", provider_id="gladia", key_tier="platform")
    assert platform_key == "sk-platform-gladia-from-env"

