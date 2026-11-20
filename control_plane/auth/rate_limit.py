"""UCVE Sliding-Window Tenant Rate Limiter."""

from __future__ import annotations

import os
import time

from core.runtime.env import is_protected_environment, is_test_env


class RateLimiter:
    """Sliding-window tenant rate limiter (default 120 req/min/tenant).

    Uses Redis INCR+EXPIRE when REDIS_URL is set and UCVE_ENV != test.
    Process-local fallback only in test (or when Redis unavailable).
    """

    def __init__(
        self,
        limit_per_min: int = 120,
        redis_url: str | None = None,
    ) -> None:
        self.limit_per_min = limit_per_min
        self._history: dict[str, list[float]] = {}
        self._redis = None
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        if url and not is_test_env():
            try:
                from core.redis.client import sync_redis_from_url

                self._redis = sync_redis_from_url(url)
            except Exception:
                self._redis = None

    def is_allowed(self, tenant_id: str, limit_override: int | None = None) -> bool:
        """Check if tenant request is within rate limit window."""
        limit = limit_override or self.limit_per_min
        if self._redis is not None:
            key = f"ucve:ratelimit:{tenant_id}"
            try:
                count = self._redis.incr(key)
                if count == 1:
                    self._redis.expire(key, 60)
                return int(count) <= limit
            except Exception:
                if is_protected_environment():
                    return False

        if is_protected_environment():
            # Redis was expected but unavailable — fail closed outside test.
            return False

        now = time.time()
        window_start = now - 60.0
        timestamps = self._history.setdefault(tenant_id, [])
        self._history[tenant_id] = [t for t in timestamps if t > window_start]
        if len(self._history[tenant_id]) >= limit:
            return False
        self._history[tenant_id].append(now)
        return True
