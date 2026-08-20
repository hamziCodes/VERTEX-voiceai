"""UCVE Tenant Secret Vault & Key Resolution Engine."""

from __future__ import annotations

import os
from typing import Any, Callable

from core.secrets.cache import SecretCache
from core.secrets.envelope import EnvelopeEncryption
from core.secrets.exceptions import DecryptionError, SecretNotFoundError
from core.secrets.kms import KMSBackend
from core.secrets.kms.local_dev import LocalDevKMSBackend


class PlatformSecrets:
    """Fallback provider API keys for platform-managed tenant tier (env only)."""

    @classmethod
    def get_platform_key(cls, provider_id: str) -> str | None:
        env_key = os.getenv(f"PLATFORM_{provider_id.upper()}_API_KEY")
        if env_key and env_key.strip():
            return env_key.strip()
        return None


class SecretVault:
    """Tenant credential vault managing store, resolve, rotation, and envelope encryption."""

    def __init__(self, kms_backend: KMSBackend | None = None) -> None:
        self.envelope = EnvelopeEncryption(kms_backend=kms_backend or LocalDevKMSBackend())
        self.cache = SecretCache()
        self._in_memory_db: dict[str, tuple[str, int]] = {}
        self.audit_hooks: list[Callable[[str, str, str], None]] = []

    def register_audit_hook(self, hook: Callable[[str, str, str], None]) -> None:
        """Register audit callback for decrypt/resolve operations (Phase 12 integration)."""
        self.audit_hooks.append(hook)

    def _make_db_key(self, tenant_id: str, provider_id: str, credential_type: str) -> str:
        return f"{tenant_id}:{provider_id}:{credential_type}"

    def store(
        self, tenant_id: str, provider_id: str, secret: str, credential_type: str = "api_key"
    ) -> None:
        """Encrypt and store tenant provider credential."""
        if not secret:
            raise ValueError("Secret value cannot be empty.")

        blob, key_version = self.envelope.encrypt_secret(secret)
        db_key = self._make_db_key(tenant_id, provider_id, credential_type)
        self._in_memory_db[db_key] = (blob, key_version)
        self.cache.invalidate(tenant_id, provider_id)

    def resolve(
        self,
        tenant_id: str,
        provider_id: str,
        credential_type: str = "api_key",
        key_tier: str = "platform",
    ) -> str:
        """Resolve decrypted API key for tenant with cache lookup and platform fallback."""
        # 1. Check cache
        cached = self.cache.get(tenant_id, provider_id)
        if cached:
            self._notify_audit_hooks(tenant_id, provider_id, "resolve_cached")
            return cached

        # 2. Check tenant vault database store
        db_key = self._make_db_key(tenant_id, provider_id, credential_type)
        if db_key in self._in_memory_db:
            blob, key_version = self._in_memory_db[db_key]
            try:
                secret = self.envelope.decrypt_secret(blob, key_version=key_version)
                self.cache.set(tenant_id, provider_id, secret)
                self._notify_audit_hooks(tenant_id, provider_id, "resolve_decrypted")
                return secret
            except DecryptionError as exc:
                raise DecryptionError(f"Failed to decrypt secret for tenant '{tenant_id}' provider '{provider_id}'.") from exc

        # 3. If key_tier == 'platform', fallback to platform-managed keys
        if key_tier == "platform":
            platform_key = PlatformSecrets.get_platform_key(provider_id)
            if platform_key:
                self.cache.set(tenant_id, provider_id, platform_key)
                self._notify_audit_hooks(tenant_id, provider_id, "resolve_platform_fallback")
                return platform_key

        raise SecretNotFoundError(
            f"No valid credential found for tenant '{tenant_id}' provider '{provider_id}' (tier: {key_tier})."
        )

    def rotate(
        self, tenant_id: str, provider_id: str, new_secret: str, credential_type: str = "api_key"
    ) -> None:
        """Rotate tenant credential and evict cached secret."""
        self.store(tenant_id, provider_id, new_secret, credential_type=credential_type)

    def _notify_audit_hooks(self, tenant_id: str, provider_id: str, action: str) -> None:
        for hook in self.audit_hooks:
            try:
                hook(tenant_id, provider_id, action)
            except Exception:
                pass
