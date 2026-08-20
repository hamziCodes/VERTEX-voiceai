"""UCVE Replay Nonce Cache for HMAC Session Minting."""

from __future__ import annotations

import time


class NonceStore:
    """Replay cache tracking used nonces with TTL to prevent replay attacks."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._in_memory_nonces: dict[str, float] = {}

    async def mark_used(self, tenant_id: str, nonce: str, ttl_sec: int = 60) -> None:
        """Mark nonce as used for tenant with specified TTL."""
        key = f"{tenant_id}:{nonce}"
        expire_at = time.time() + ttl_sec
        self._in_memory_nonces[key] = expire_at

    async def is_used(self, tenant_id: str, nonce: str) -> bool:
        """Return True if nonce has already been used and has not expired."""
        key = f"{tenant_id}:{nonce}"
        expire_at = self._in_memory_nonces.get(key)
        if expire_at is None:
            return False

        if time.time() > expire_at:
            del self._in_memory_nonces[key]
            return False

        return True
