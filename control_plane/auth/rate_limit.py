"""UCVE Sliding-Window Tenant Rate Limiter."""

from __future__ import annotations

import time


class RateLimiter:
    """Sliding-window tenant request rate limiter (default 120 req/min/tenant)."""

    def __init__(self, limit_per_min: int = 120) -> None:
        self.limit_per_min = limit_per_min
        self._history: dict[str, list[float]] = {}

    def is_allowed(self, tenant_id: str, limit_override: int | None = None) -> bool:
        """Check if tenant request is within rate limit window."""
        limit = limit_override or self.limit_per_min
        now = time.time()
        window_start = now - 60.0

        timestamps = self._history.setdefault(tenant_id, [])
        # Filter timestamps within window
        self._history[tenant_id] = [t for t in timestamps if t > window_start]

        if len(self._history[tenant_id]) >= limit:
            return False  # Rate limit exceeded

        self._history[tenant_id].append(now)
        return True
