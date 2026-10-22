from __future__ import annotations

from dataclasses import fields

import pytest

from core.secrets.cache import SecretCache
from core.secrets.exceptions import SecretNotFoundError
from core.secrets.kms.local_dev import LocalDevKMSBackend
from core.secrets.platform import PlatformCredential
from core.secrets.policy import CredentialTier, ResolvedCredential
from core.secrets.repository import InMemorySecretRepository
from core.secrets.vault import SecretVault


class FakePlatformSecrets:
    def __init__(self, values: dict[tuple[str, str], str]) -> None:
        self.values = values
        self.calls: list[tuple[str, str]] = []

    def resolve(
        self, provider_id: str, credential_type: str
    ) -> PlatformCredential | None:
        self.calls.append((provider_id, credential_type))
        value = self.values.get((provider_id, credential_type))
        if value is None:
            return None
        return PlatformCredential(secret=value, version="platform-v1")


def _vault(platform: FakePlatformSecrets | None = None) -> SecretVault:
    return SecretVault(
        kms_backend=LocalDevKMSBackend(master_key="phase-07b-test-key"),
        repository=InMemorySecretRepository(),
        platform_secrets=platform or FakePlatformSecrets({}),
    )


def test_platform_never_uses_tenant_secret() -> None:
    platform = FakePlatformSecrets({("gladia", "api_key"): "platform-secret"})
    vault = _vault(platform)
    vault.store(
        "tenant-a",
        "gladia",
        "tenant-secret",
        credential_ref="tenant-key",
    )

    resolved = vault.resolve_credential(
        "tenant-a",
        "gladia",
        credential_ref=None,
        tier=CredentialTier.PLATFORM,
    )

    assert resolved.secret == "platform-secret"
    assert resolved.source_tier is CredentialTier.PLATFORM
    assert resolved.credential_ref is None


def test_byok_never_falls_back_to_platform() -> None:
    platform = FakePlatformSecrets({("gladia", "api_key"): "platform-secret"})
    vault = _vault(platform)

    with pytest.raises(SecretNotFoundError, match="tenant credential"):
        vault.resolve_credential(
            "tenant-a",
            "gladia",
            credential_ref="missing-key",
            tier=CredentialTier.BYOK,
        )

    assert platform.calls == []


def test_both_prefers_byok_then_explicit_platform() -> None:
    platform = FakePlatformSecrets({("groq", "api_key"): "platform-groq"})
    vault = _vault(platform)
    vault.store(
        "tenant-a",
        "groq",
        "tenant-groq",
        credential_ref="tenant-key",
    )

    tenant = vault.resolve_credential(
        "tenant-a",
        "groq",
        credential_ref="tenant-key",
        tier=CredentialTier.BOTH,
    )
    fallback = vault.resolve_credential(
        "tenant-b",
        "groq",
        credential_ref="missing-key",
        tier=CredentialTier.BOTH,
    )

    assert tenant.secret == "tenant-groq"
    assert tenant.source_tier is CredentialTier.BYOK
    assert fallback.secret == "platform-groq"
    assert fallback.source_tier is CredentialTier.PLATFORM


def test_cache_identity_isolates_tenant_ref_type_tier_and_version() -> None:
    vault = _vault()
    vault.store(
        "tenant-a",
        "openai",
        "a-primary",
        credential_ref="primary",
    )
    vault.store(
        "tenant-a",
        "openai",
        "a-secondary",
        credential_ref="secondary",
    )
    vault.store(
        "tenant-b",
        "openai",
        "b-primary",
        credential_ref="primary",
    )
    vault.store(
        "tenant-a",
        "openai",
        "a-oauth",
        credential_type="oauth_token",
        credential_ref="primary",
    )

    assert (
        vault.resolve_credential(
            "tenant-a", "openai", credential_ref="primary", tier="byok"
        ).secret
        == "a-primary"
    )
    assert (
        vault.resolve_credential(
            "tenant-a", "openai", credential_ref="secondary", tier="byok"
        ).secret
        == "a-secondary"
    )
    assert (
        vault.resolve_credential(
            "tenant-b", "openai", credential_ref="primary", tier="byok"
        ).secret
        == "b-primary"
    )
    assert (
        vault.resolve_credential(
            "tenant-a",
            "openai",
            credential_ref="primary",
            credential_type="oauth_token",
            tier="byok",
        ).secret
        == "a-oauth"
    )
    assert len(vault.cache) == 4


def test_rotation_evicts_old_version() -> None:
    vault = _vault()
    first = vault.store(
        "tenant-a",
        "deepgram",
        "old-secret",
        credential_ref="speech-key",
    )
    before = vault.resolve_credential(
        "tenant-a",
        "deepgram",
        credential_ref="speech-key",
        tier="byok",
    )

    second = vault.rotate(
        "tenant-a",
        "deepgram",
        "new-secret",
        credential_ref="speech-key",
    )
    after = vault.resolve_credential(
        "tenant-a",
        "deepgram",
        credential_ref="speech-key",
        tier="byok",
    )

    assert before.secret == "old-secret"
    assert after.secret == "new-secret"
    assert second.rotation_version == first.rotation_version + 1
    assert after.rotation_version == second.rotation_version
    assert len(vault.cache) == 1


def test_revocation_evicts_cached_credential_and_fails_closed() -> None:
    vault = _vault()
    vault.store(
        "tenant-a",
        "deepgram",
        "revoked-secret",
        credential_ref="speech-key",
    )
    vault.resolve_credential(
        "tenant-a",
        "deepgram",
        credential_ref="speech-key",
        tier="byok",
    )

    assert len(vault.cache) == 1
    assert vault.revoke("tenant-a", "deepgram", credential_ref="speech-key") is True
    assert len(vault.cache) == 0
    with pytest.raises(SecretNotFoundError, match="tenant credential"):
        vault.resolve_credential(
            "tenant-a",
            "deepgram",
            credential_ref="speech-key",
            tier="byok",
        )


def test_secret_cache_ttl_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UCVE_SECRET_CACHE_TTL_SEC", raising=False)

    assert SecretCache(default_ttl_sec=-1).ttl_sec == 1.0
    assert SecretCache(default_ttl_sec=99_999).ttl_sec == 3600.0


def test_resolved_credential_repr_omits_secret() -> None:
    names = {item.name for item in fields(ResolvedCredential)}
    assert "secret" in names

    resolved = ResolvedCredential(
        tenant_id="tenant-a",
        provider_id="cartesia",
        credential_type="api_key",
        requested_tier=CredentialTier.BOTH,
        source_tier=CredentialTier.BYOK,
        credential_ref="voice-key",
        rotation_version=3,
        secret="must-not-appear",
    )

    assert "must-not-appear" not in repr(resolved)
    assert "must-not-appear" not in str(resolved)
