"""UCVE Replay Nonce Cache for HMAC Session Minting."""

from __future__ import annotations

import os
import time

from core.runtime.env import is_test_env


class NonceStore:
    """Replay cache: Redis when REDIS_URL set; in-memory for test/dev without Redis."""

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis_url = url
        self._redis: object | None = None
        self._in_memory_nonces: dict[str, float] = {}
        if url and not is_test_env():
            try:
                import redis.asyncio as redis_async

                self._redis = redis_async.from_url(url, decode_responses=True)
            except Exception:
                self._redis = None

    def _key(self, tenant_id: str, nonce: str) -> str:
        return f"ucve:nonce:{tenant_id}:{nonce}"

    async def mark_used(self, tenant_id: str, nonce: str, ttl_sec: int = 60) -> None:
        """Mark nonce as used for tenant with specified TTL."""
        key = self._key(tenant_id, nonce)
        if self._redis is not None:
            await self._redis.set(key, "1", ex=ttl_sec)  # type: ignore[union-attr]
            return
        self._in_memory_nonces[f"{tenant_id}:{nonce}"] = time.time() + ttl_sec

    async def is_used(self, tenant_id: str, nonce: str) -> bool:
        """Return True if nonce has already been used and has not expired."""
        if self._redis is not None:
            return bool(await self._redis.exists(self._key(tenant_id, nonce)))  # type: ignore[union-attr]

        key = f"{tenant_id}:{nonce}"
        expire_at = self._in_memory_nonces.get(key)
        if expire_at is None:
            return False
        if time.time() > expire_at:
            del self._in_memory_nonces[key]
            return False
        return True
