"""UCVE In-Process Secret TTL Cache."""

from __future__ import annotations

import os
import time
from typing import Any


class SecretCache:
    """In-process TTL cache for resolved tenant credentials."""

    def __init__(self, default_ttl_sec: float | None = None, max_entries: int = 1000) -> None:
        env_ttl = os.getenv("UCVE_SECRET_CACHE_TTL_SEC")
        self.ttl_sec = float(env_ttl) if env_ttl else (default_ttl_sec or 600.0)
        self.max_entries = max_entries
        self._store: dict[str, tuple[str, float]] = {}

    def _make_key(self, tenant_id: str, provider_id: str) -> str:
        return f"{tenant_id}:{provider_id}"

    def get(self, tenant_id: str, provider_id: str) -> str | None:
        """Retrieve cached secret if not expired."""
        key = self._make_key(tenant_id, provider_id)
        if key not in self._store:
            return None

        secret, expires_at = self._store[key]
        if time.time() >= expires_at:
            del self._store[key]
            return None

        return secret

    def set(self, tenant_id: str, provider_id: str, secret: str) -> None:
        """Store secret in cache with TTL expiry."""
        if len(self._store) >= self.max_entries:
            # Evict oldest entry
            oldest_key = min(self._store.keys(), key=lambda k: self._store[k][1])
            del self._store[oldest_key]

        key = self._make_key(tenant_id, provider_id)
        expires_at = time.time() + self.ttl_sec
        self._store[key] = (secret, expires_at)

    def invalidate(self, tenant_id: str, provider_id: str) -> None:
        """Explicitly evict secret from cache (e.g. on rotate/revoke)."""
        key = self._make_key(tenant_id, provider_id)
        self._store.pop(key, None)

    def clear(self) -> None:
        """Clear all cached credentials."""
        self._store.clear()
