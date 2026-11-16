"""Atomic replay protection for signed session-mint nonces."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from core.runtime.env import is_protected_environment, is_test_env


class ReplayStoreUnavailableError(RuntimeError):
    """Raised when a protected runtime cannot reach its replay store."""


class NonceStore:
    """Consume tenant nonces atomically with Redis or a locked local test store."""

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        redis_client: Any | None = None,
    ) -> None:
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis_url = url
        self._redis: Any | None = redis_client
        self._in_memory_nonces: dict[str, float] = {}
        self._lock = asyncio.Lock()
        if self._redis is None and url and not is_test_env():
            try:
                from core.redis.client import async_redis_from_url

                self._redis = async_redis_from_url(url)
            except Exception:
                self._redis = None

    def _key(self, tenant_id: str, nonce: str) -> str:
        return f"ucve:nonce:{tenant_id}:{nonce}"

    def _require_runtime_store(self) -> None:
        if self._redis is None and is_protected_environment():
            raise ReplayStoreUnavailableError(
                "Replay protection is unavailable in this environment."
            )

    async def consume_once(self, tenant_id: str, nonce: str, ttl_sec: int = 60) -> bool:
        """Atomically claim a nonce; exactly one concurrent caller succeeds."""
        if not tenant_id or not nonce or ttl_sec <= 0:
            return False
        self._require_runtime_store()
        if self._redis is not None:
            try:
                return bool(
                    await self._redis.set(
                        self._key(tenant_id, nonce), "1", ex=ttl_sec, nx=True
                    )
                )
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Replay protection is unavailable in this environment."
                ) from exc

        key = f"{tenant_id}:{nonce}"
        now = time.time()
        async with self._lock:
            self._purge_expired(now)
            if key in self._in_memory_nonces:
                return False
            self._in_memory_nonces[key] = now + ttl_sec
            return True

    async def mark_used(self, tenant_id: str, nonce: str, ttl_sec: int = 60) -> None:
        """Compatibility wrapper; prefer :meth:`consume_once`."""
        await self.consume_once(tenant_id, nonce, ttl_sec)

    async def is_used(self, tenant_id: str, nonce: str) -> bool:
        """Read replay state without claiming it."""
        self._require_runtime_store()
        if self._redis is not None:
            try:
                return bool(await self._redis.exists(self._key(tenant_id, nonce)))
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Replay protection is unavailable in this environment."
                ) from exc
        key = f"{tenant_id}:{nonce}"
        now = time.time()
        async with self._lock:
            self._purge_expired(now)
            return key in self._in_memory_nonces

    def _purge_expired(self, now: float) -> None:
        expired = [
            key
            for key, expires_at in self._in_memory_nonces.items()
            if expires_at <= now
        ]
        for key in expired:
            del self._in_memory_nonces[key]
