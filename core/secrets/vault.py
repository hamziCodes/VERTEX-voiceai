"""UCVE Tenant Secret Vault & Key Resolution Engine."""

from __future__ import annotations

from collections.abc import Callable

from core.secrets.cache import CredentialCacheKey, SecretCache
from core.secrets.envelope import EnvelopeEncryption
from core.secrets.exceptions import DecryptionError, SecretNotFoundError
from core.secrets.kms import KMSBackend
from core.secrets.kms.local_dev import LocalDevKMSBackend
from core.secrets.platform import (
    EnvironmentPlatformSecretProvider,
    PlatformSecretProvider,
)
from core.secrets.policy import CredentialTier, ResolvedCredential
from core.secrets.repository import (
    CredentialRecord,
    InMemorySecretRepository,
    SecretRepository,
)


class PlatformSecrets:
    """Compatibility wrapper for the injected platform-secret boundary."""

    @classmethod
    def get_platform_key(cls, provider_id: str) -> str | None:
        resolved = EnvironmentPlatformSecretProvider().resolve(provider_id, "api_key")
        return resolved.secret if resolved is not None else None


class SecretVault:
    """Tenant credential vault managing store, resolve, rotation, and envelope encryption."""

    def __init__(
        self,
        kms_backend: KMSBackend | None = None,
        *,
        repository: SecretRepository | None = None,
        platform_secrets: PlatformSecretProvider | None = None,
        cache: SecretCache | None = None,
    ) -> None:
        self._kms_backend = kms_backend
        self._envelope: EnvelopeEncryption | None = None
        self.repository = repository or InMemorySecretRepository()
        self.platform_secrets = platform_secrets or EnvironmentPlatformSecretProvider()
        self.cache = cache or SecretCache()
        self._in_memory_db = (
            self.repository.storage
            if isinstance(self.repository, InMemorySecretRepository)
            else {}
        )
        self.audit_hooks: list[Callable[[str, str, str], None]] = []

    @property
    def envelope(self) -> EnvelopeEncryption:
        """Create KMS-backed encryption only when a tenant secret needs it."""
        if self._envelope is None:
            self._envelope = EnvelopeEncryption(
                kms_backend=self._kms_backend or LocalDevKMSBackend()
            )
        return self._envelope

    def register_audit_hook(self, hook: Callable[[str, str, str], None]) -> None:
        """Register audit callback for decrypt/resolve operations (Phase 12 integration)."""
        self.audit_hooks.append(hook)

    def _make_db_key(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str,
        credential_ref: str = "default",
    ) -> str:
        return InMemorySecretRepository.make_key(
            tenant_id, provider_id, credential_type, credential_ref
        )

    def store(
        self,
        tenant_id: str,
        provider_id: str,
        secret: str,
        credential_type: str = "api_key",
        *,
        credential_ref: str = "default",
    ) -> CredentialRecord:
        """Encrypt and store tenant provider credential."""
        if not secret:
            raise ValueError("Secret value cannot be empty.")

        blob, key_version = self.envelope.encrypt_secret(secret)
        previous = self.repository.get(
            tenant_id, provider_id, credential_type, credential_ref
        )
        record = CredentialRecord(
            tenant_id=tenant_id,
            provider_id=provider_id,
            credential_type=credential_type,
            credential_ref=credential_ref,
            encrypted_blob=blob,
            key_version=key_version,
            rotation_version=(previous.rotation_version + 1 if previous else 1),
        )
        self.repository.put(record)
        self.cache.invalidate(
            tenant_id=tenant_id,
            provider_id=provider_id,
            credential_type=credential_type,
            credential_ref=credential_ref,
        )
        return record

    def resolve_credential(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        credential_ref: str | None,
        credential_type: str = "api_key",
        tier: CredentialTier | str = CredentialTier.PLATFORM,
    ) -> ResolvedCredential:
        """Resolve one credential according to the published source policy."""
        requested_tier = CredentialTier(tier)
        normalized_provider = provider_id.strip().lower()

        if requested_tier in {CredentialTier.BYOK, CredentialTier.BOTH}:
            tenant_record = (
                self.repository.get(
                    tenant_id,
                    normalized_provider,
                    credential_type,
                    credential_ref,
                )
                if credential_ref
                else None
            )
            if tenant_record is not None:
                key = CredentialCacheKey(
                    tenant_id=tenant_id,
                    provider_id=normalized_provider,
                    credential_type=credential_type,
                    requested_tier=requested_tier,
                    credential_ref=credential_ref,
                    rotation_version=tenant_record.rotation_version,
                )
                cached = self.cache.get(key)
                if cached is not None:
                    self._notify_audit_hooks(
                        tenant_id, normalized_provider, "resolve_cached"
                    )
                    return cached
                try:
                    secret = self.envelope.decrypt_secret(
                        tenant_record.encrypted_blob,
                        key_version=tenant_record.key_version,
                    )
                except DecryptionError as exc:
                    raise DecryptionError(
                        "Failed to decrypt tenant credential for "
                        f"provider '{normalized_provider}'."
                    ) from exc
                resolved = ResolvedCredential(
                    tenant_id=tenant_id,
                    provider_id=normalized_provider,
                    credential_type=credential_type,
                    requested_tier=requested_tier,
                    source_tier=CredentialTier.BYOK,
                    credential_ref=credential_ref,
                    rotation_version=tenant_record.rotation_version,
                    secret=secret,
                )
                self.cache.set(key, resolved)
                self._notify_audit_hooks(
                    tenant_id, normalized_provider, "resolve_decrypted"
                )
                return resolved
            if requested_tier is CredentialTier.BYOK:
                raise SecretNotFoundError(
                    "No tenant credential found for "
                    f"provider '{normalized_provider}' and reference "
                    f"'{credential_ref or ''}'."
                )

        platform = self.platform_secrets.resolve(normalized_provider, credential_type)
        if platform is None:
            raise SecretNotFoundError(
                "No platform credential found for "
                f"provider '{normalized_provider}' and type '{credential_type}'."
            )
        key = CredentialCacheKey(
            tenant_id=tenant_id,
            provider_id=normalized_provider,
            credential_type=credential_type,
            requested_tier=requested_tier,
            credential_ref=None,
            rotation_version=platform.version,
        )
        cached = self.cache.get(key)
        if cached is not None:
            self._notify_audit_hooks(tenant_id, normalized_provider, "resolve_cached")
            return cached
        resolved = ResolvedCredential(
            tenant_id=tenant_id,
            provider_id=normalized_provider,
            credential_type=credential_type,
            requested_tier=requested_tier,
            source_tier=CredentialTier.PLATFORM,
            credential_ref=None,
            rotation_version=platform.version,
            secret=platform.secret,
        )
        self.cache.set(key, resolved)
        self._notify_audit_hooks(tenant_id, normalized_provider, "resolve_platform")
        return resolved

    def resolve(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str = "api_key",
        key_tier: str = "platform",
    ) -> str:
        """Compatibility wrapper; new runtime code uses ``resolve_credential``."""
        legacy_tier = (
            CredentialTier.BOTH if key_tier == "platform" else CredentialTier(key_tier)
        )
        return self.resolve_credential(
            tenant_id,
            provider_id,
            credential_ref="default",
            credential_type=credential_type,
            tier=legacy_tier,
        ).secret

    def rotate(
        self,
        tenant_id: str,
        provider_id: str,
        new_secret: str,
        credential_type: str = "api_key",
        *,
        credential_ref: str = "default",
    ) -> CredentialRecord:
        """Rotate tenant credential and evict cached secret."""
        return self.store(
            tenant_id,
            provider_id,
            new_secret,
            credential_type=credential_type,
            credential_ref=credential_ref,
        )

    def revoke(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str = "api_key",
        *,
        credential_ref: str = "default",
    ) -> bool:
        """Delete a tenant credential and immediately evict derived cache entries."""
        removed = self.repository.delete(
            tenant_id,
            provider_id,
            credential_type,
            credential_ref,
        )
        self.cache.invalidate(
            tenant_id=tenant_id,
            provider_id=provider_id,
            credential_type=credential_type,
            credential_ref=credential_ref,
        )
        if removed:
            self._notify_audit_hooks(tenant_id, provider_id, "revoke")
        return removed

    def _notify_audit_hooks(
        self, tenant_id: str, provider_id: str, action: str
    ) -> None:
        for hook in self.audit_hooks:
            try:
                hook(tenant_id, provider_id, action)
            except Exception:
                pass
