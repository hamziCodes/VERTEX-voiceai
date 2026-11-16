"""Atomic one-use and revocation state for short-lived session JWTs."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from core.redis.nonce_store import ReplayStoreUnavailableError
from core.runtime.env import is_protected_environment, is_test_env


class SessionTokenStore:
    """Track connection claims, refresh use, and revocation by tenant/JTI."""

    def __init__(
        self,
        redis_url: str | None = None,
        *,
        redis_client: Any | None = None,
    ) -> None:
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis: Any | None = redis_client
        self._memory: dict[str, float] = {}
        self._lock = asyncio.Lock()
        if self._redis is None and url and not is_test_env():
            try:
                from core.redis.client import async_redis_from_url

                self._redis = async_redis_from_url(url)
            except Exception:
                self._redis = None

    def _key(self, kind: str, tenant_id: str, jti: str) -> str:
        return f"ucve:session-token:{kind}:{tenant_id}:{jti}"

    def _require_runtime_store(self) -> None:
        if self._redis is None and is_protected_environment():
            raise ReplayStoreUnavailableError(
                "Session token state is unavailable in this environment."
            )

    async def claim_connection(self, tenant_id: str, jti: str, ttl_sec: int) -> bool:
        if not tenant_id or not jti or ttl_sec <= 0:
            return False
        self._require_runtime_store()
        revoked_key = self._key("revoked", tenant_id, jti)
        connection_key = self._key("connection", tenant_id, jti)
        if self._redis is not None:
            script = """
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            local claimed = redis.call('SET', KEYS[2], '1', 'EX', ARGV[1], 'NX')
            if claimed then return 1 end
            return 0
            """
            try:
                return bool(
                    await self._redis.eval(
                        script, 2, revoked_key, connection_key, ttl_sec
                    )
                )
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Session token state is unavailable in this environment."
                ) from exc
        now = time.time()
        async with self._lock:
            self._purge(now)
            if revoked_key in self._memory or connection_key in self._memory:
                return False
            self._memory[connection_key] = now + ttl_sec
            return True

    async def consume_refresh(self, tenant_id: str, jti: str, ttl_sec: int) -> bool:
        if not tenant_id or not jti or ttl_sec <= 0:
            return False
        self._require_runtime_store()
        refresh_key = self._key("refresh", tenant_id, jti)
        revoked_key = self._key("revoked", tenant_id, jti)
        if self._redis is not None:
            script = """
            local claimed = redis.call('SET', KEYS[1], '1', 'EX', ARGV[1], 'NX')
            if not claimed then return 0 end
            redis.call('SET', KEYS[2], '1', 'EX', ARGV[1])
            return 1
            """
            try:
                return bool(
                    await self._redis.eval(script, 2, refresh_key, revoked_key, ttl_sec)
                )
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Session token state is unavailable in this environment."
                ) from exc
        now = time.time()
        async with self._lock:
            self._purge(now)
            if refresh_key in self._memory:
                return False
            expires_at = now + ttl_sec
            self._memory[refresh_key] = expires_at
            self._memory[revoked_key] = expires_at
            return True

    async def revoke(self, tenant_id: str, jti: str, ttl_sec: int) -> None:
        self._require_runtime_store()
        key = self._key("revoked", tenant_id, jti)
        if self._redis is not None:
            try:
                await self._redis.set(key, "1", ex=ttl_sec)
                return
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Session token state is unavailable in this environment."
                ) from exc
        async with self._lock:
            self._memory[key] = time.time() + ttl_sec

    async def is_revoked(self, tenant_id: str, jti: str) -> bool:
        self._require_runtime_store()
        key = self._key("revoked", tenant_id, jti)
        if self._redis is not None:
            try:
                return bool(await self._redis.exists(key))
            except Exception as exc:
                # A configured store that fails is unavailable, never "used"
                # or "not revoked": guessing would report a fake replay or
                # silently drop a revocation.
                raise ReplayStoreUnavailableError(
                    "Session token state is unavailable in this environment."
                ) from exc
        now = time.time()
        async with self._lock:
            self._purge(now)
            return key in self._memory

    def _purge(self, now: float) -> None:
        expired = [key for key, expires_at in self._memory.items() if expires_at <= now]
        for key in expired:
            del self._memory[key]
