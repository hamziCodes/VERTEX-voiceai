"""UCVE In-Process Secret TTL Cache."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from core.secrets.policy import CredentialTier, ResolvedCredential


@dataclass(frozen=True, slots=True)
class CredentialCacheKey:
    """Complete non-secret identity for one cached credential version."""

    tenant_id: str
    provider_id: str
    credential_type: str
    requested_tier: CredentialTier
    credential_ref: str | None
    rotation_version: int | str


class SecretCache:
    """In-process TTL cache for resolved tenant credentials."""

    def __init__(
        self, default_ttl_sec: float | None = None, max_entries: int = 1000
    ) -> None:
        env_ttl = os.getenv("UCVE_SECRET_CACHE_TTL_SEC")
        requested_ttl = (
            float(env_ttl)
            if env_ttl
            else (600.0 if default_ttl_sec is None else float(default_ttl_sec))
        )
        self.ttl_sec = min(3600.0, max(1.0, requested_ttl))
        self.max_entries = max(1, int(max_entries))
        self._store: dict[CredentialCacheKey, tuple[ResolvedCredential, float]] = {}

    def __len__(self) -> int:
        return len(self._store)

    def get(self, key: CredentialCacheKey) -> ResolvedCredential | None:
        """Retrieve cached secret if not expired."""
        if key not in self._store:
            return None

        credential, expires_at = self._store[key]
        if time.time() >= expires_at:
            del self._store[key]
            return None

        return credential

    def set(self, key: CredentialCacheKey, credential: ResolvedCredential) -> None:
        """Store secret in cache with TTL expiry."""
        if len(self._store) >= self.max_entries:
            # Evict oldest entry
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k][1])
            del self._store[oldest_key]

        expires_at = time.time() + self.ttl_sec
        self._store[key] = (credential, expires_at)

    def invalidate(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        credential_type: str | None = None,
        credential_ref: str | None = None,
    ) -> None:
        """Evict every cached version derived from a credential identity."""
        stale = [
            key
            for key in self._store
            if key.tenant_id == tenant_id
            and key.provider_id == provider_id
            and (credential_type is None or key.credential_type == credential_type)
            and (credential_ref is None or key.credential_ref == credential_ref)
        ]
        for key in stale:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached credentials."""
        self._store.clear()
