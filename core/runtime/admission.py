"""Atomic Redis-backed session admission leases with local test fallback."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from typing import Any

from core.errors.codes import UCVEErrorCode
from core.runtime.env import is_protected_environment, is_test_env
from core.runtime.profile_loader import RuntimeProfile, load_profile

_ACQUIRE_LUA = """
local now = tonumber(ARGV[3])
local expires = tonumber(ARGV[4])
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now)
if redis.call('EXISTS', KEYS[1]) == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[5]))
  redis.call('ZADD', KEYS[2], expires, ARGV[1])
  redis.call('ZADD', KEYS[3], expires, ARGV[1])
  return 1
end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[6]) then return 0 end
if redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[7]) then return 0 end
redis.call('SET', KEYS[1], ARGV[2], 'EX', tonumber(ARGV[5]), 'NX')
redis.call('ZADD', KEYS[2], expires, ARGV[1])
redis.call('ZADD', KEYS[3], expires, ARGV[1])
return 1
"""

_RELEASE_LUA = """
redis.call('DEL', KEYS[1])
redis.call('ZREM', KEYS[2], ARGV[1])
redis.call('ZREM', KEYS[3], ARGV[1])
return 1
"""

_HEARTBEAT_LUA = """
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
redis.call('ZADD', KEYS[2], tonumber(ARGV[2]), ARGV[1])
redis.call('ZADD', KEYS[3], tonumber(ARGV[2]), ARGV[1])
return 1
"""

_COUNT_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', tonumber(ARGV[1]))
return redis.call('ZCARD', KEYS[1])
"""


class CapacityExceededError(Exception):
    """Raised when worker or tenant concurrency has reached its limit."""

    def __init__(self, message: str = "Worker capacity limit reached") -> None:
        super().__init__(message)
        self.error_code = UCVEErrorCode.QUOTA_EXCEEDED
        self.status_code = 503


class AdmissionStoreUnavailableError(RuntimeError):
    """Raised when protected admission state cannot be reached."""


def cluster_session_capacity(profile: RuntimeProfile | None = None) -> int:
    """Cluster-wide concurrent session cap enforced by shared admission.

    ``max_sessions_per_worker`` is a *per-process* limit (each worker enforces
    it locally and reports not-ready when full). The shared Redis admission
    key counts sessions across the whole fleet, so its cap must be the fleet
    capacity: ``UCVE_CLUSTER_MAX_SESSIONS`` when set, otherwise
    ``max_sessions_per_worker * UCVE_WORKER_REPLICAS`` (default one replica).
    """
    selected = profile or load_profile()
    explicit = (os.environ.get("UCVE_CLUSTER_MAX_SESSIONS") or "").strip()
    if explicit:
        value = int(explicit)
        if value < 1:
            raise ValueError("UCVE_CLUSTER_MAX_SESSIONS must be positive.")
        return value
    replicas = int((os.environ.get("UCVE_WORKER_REPLICAS") or "1").strip() or "1")
    if replicas < 1:
        raise ValueError("UCVE_WORKER_REPLICAS must be positive.")
    return selected.max_sessions_per_worker * replicas


class SessionAdmissionController:
    """Acquire expiring session leases atomically across control plane/workers."""

    def __init__(
        self,
        profile: RuntimeProfile | None = None,
        max_sessions: int | None = None,
        *,
        redis_client: Any | None = None,
        lease_ttl_sec: int = 120,
        force_memory: bool = False,
        clock: Callable[[], float] = time.time,
        key_prefix: str = "ucve:admission",
    ) -> None:
        self.profile = profile or load_profile()
        self.max_sessions = (
            max_sessions
            if max_sessions is not None
            else cluster_session_capacity(self.profile)
        )
        self.lease_ttl_sec = max(10, lease_ttl_sec)
        self.clock = clock
        self.key_prefix = key_prefix.rstrip(":")
        self._lock = asyncio.Lock()
        self._leases: dict[str, tuple[str, float]] = {}
        self._redis = redis_client
        redis_url = (os.environ.get("REDIS_URL") or "").strip()
        memory_mode = force_memory or (
            is_test_env()
            and not is_protected_environment()
            and redis_client is None
        )
        if self._redis is None and not memory_mode and redis_url:
            from redis.asyncio import Redis

            self._redis = Redis.from_url(redis_url, decode_responses=True)
        if self._redis is None and not memory_mode and is_protected_environment():
            raise AdmissionStoreUnavailableError(
                "Protected environments require Redis admission state."
            )

    @property
    def active_session_count(self) -> int:
        self._purge_memory_expired()
        return len(self._leases)

    def can_admit(self) -> bool:
        return self.active_session_count < self.max_sessions

    def _purge_memory_expired(self) -> int:
        now = self.clock()
        expired = [
            session_id
            for session_id, (_tenant_id, expires_at) in self._leases.items()
            if expires_at <= now
        ]
        for session_id in expired:
            self._leases.pop(session_id, None)
        return len(expired)

    def _keys(self, session_id: str, tenant_id: str) -> tuple[str, str, str]:
        return (
            f"{self.key_prefix}:session:{session_id}",
            f"{self.key_prefix}:tenant:{tenant_id}",
            f"{self.key_prefix}:global",
        )

    async def acquire(
        self,
        session_id: str,
        tenant_id: str | None = None,
        *,
        max_tenant_sessions: int | None = None,
    ) -> bool:
        tenant = (tenant_id or "_global").strip()
        tenant_limit = max_tenant_sessions or self.max_sessions
        if self._redis is not None:
            now_ms = int(self.clock() * 1000)
            expires_ms = now_ms + self.lease_ttl_sec * 1000
            try:
                admitted = await self._redis.eval(
                    _ACQUIRE_LUA,
                    3,
                    *self._keys(session_id, tenant),
                    session_id,
                    tenant,
                    now_ms,
                    expires_ms,
                    self.lease_ttl_sec,
                    tenant_limit,
                    self.max_sessions,
                )
            except Exception as exc:
                raise AdmissionStoreUnavailableError(
                    "Admission state is unavailable."
                ) from exc
            if int(admitted) != 1:
                raise CapacityExceededError("Concurrent session limit reached.")
            self._leases[session_id] = (
                tenant,
                self.clock() + self.lease_ttl_sec,
            )
            return True
        async with self._lock:
            self._purge_memory_expired()
            if session_id in self._leases:
                self._leases[session_id] = (
                    tenant,
                    self.clock() + self.lease_ttl_sec,
                )
                return True
            tenant_count = sum(
                1 for current_tenant, _expiry in self._leases.values()
                if current_tenant == tenant
            )
            if len(self._leases) >= self.max_sessions or tenant_count >= tenant_limit:
                raise CapacityExceededError("Concurrent session limit reached.")
            self._leases[session_id] = (
                tenant,
                self.clock() + self.lease_ttl_sec,
            )
            return True

    async def heartbeat(self, session_id: str, tenant_id: str) -> bool:
        tenant = tenant_id.strip()
        if self._redis is not None:
            expires_ms = int((self.clock() + self.lease_ttl_sec) * 1000)
            try:
                refreshed = await self._redis.eval(
                    _HEARTBEAT_LUA,
                    3,
                    *self._keys(session_id, tenant),
                    session_id,
                    expires_ms,
                    self.lease_ttl_sec,
                )
            except Exception as exc:
                raise AdmissionStoreUnavailableError(
                    "Admission state is unavailable."
                ) from exc
            if int(refreshed) == 1:
                self._leases[session_id] = (
                    tenant,
                    self.clock() + self.lease_ttl_sec,
                )
                return True
            return False
        async with self._lock:
            self._purge_memory_expired()
            if session_id not in self._leases:
                return False
            self._leases[session_id] = (
                tenant,
                self.clock() + self.lease_ttl_sec,
            )
            return True

    async def release(self, session_id: str, tenant_id: str | None = None) -> None:
        known_tenant = self._leases.get(session_id, (tenant_id or "_global", 0.0))[0]
        tenant = (tenant_id or known_tenant).strip()
        if self._redis is not None:
            try:
                await self._redis.eval(
                    _RELEASE_LUA,
                    3,
                    *self._keys(session_id, tenant),
                    session_id,
                )
            except Exception as exc:
                raise AdmissionStoreUnavailableError(
                    "Admission state is unavailable."
                ) from exc
        async with self._lock:
            self._leases.pop(session_id, None)

    async def reconcile(self) -> int:
        if self._redis is not None:
            try:
                removed = await self._redis.zremrangebyscore(
                    f"{self.key_prefix}:global",
                    "-inf",
                    int(self.clock() * 1000),
                )
            except Exception as exc:
                raise AdmissionStoreUnavailableError(
                    "Admission state is unavailable."
                ) from exc
            async with self._lock:
                local_removed = self._purge_memory_expired()
            return max(int(removed), local_removed)
        async with self._lock:
            return self._purge_memory_expired()

    async def current_tenant_count(self, tenant_id: str) -> int:
        """Return the current tenant lease count after removing expired leases."""
        tenant = tenant_id.strip()
        if self._redis is not None:
            try:
                count = await self._redis.eval(
                    _COUNT_LUA,
                    1,
                    f"{self.key_prefix}:tenant:{tenant}",
                    int(self.clock() * 1000),
                )
            except Exception as exc:
                raise AdmissionStoreUnavailableError(
                    "Admission state is unavailable."
                ) from exc
            return int(count)
        async with self._lock:
            self._purge_memory_expired()
            return sum(
                1
                for current_tenant, _expiry in self._leases.values()
                if current_tenant == tenant
            )

    def acquire_sync(self, session_id: str) -> bool:
        """Local compatibility method; durable callers must use ``acquire``."""

        if self._redis is not None:
            raise RuntimeError("Redis admission requires async acquire().")
        self._purge_memory_expired()
        if session_id in self._leases:
            return True
        if len(self._leases) >= self.max_sessions:
            raise CapacityExceededError("Concurrent session limit reached.")
        self._leases[session_id] = (
            "_global",
            self.clock() + self.lease_ttl_sec,
        )
        return True

    def release_sync(self, session_id: str) -> None:
        """Local compatibility method; durable callers must use ``release``."""

        if self._redis is not None:
            raise RuntimeError("Redis admission requires async release().")
        self._leases.pop(session_id, None)
