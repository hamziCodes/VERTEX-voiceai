"""UCVE Tenant Quota Enforcer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.metering.quota_limits import QuotaLimits


@dataclass
class QuotaCheckResult:
    """Result of tenant quota admission check."""

    allowed: bool
    reason: str | None = None
    is_soft_cap_warn: bool = False


class QuotaEnforcer:
    """Quota enforcer checking concurrent and monthly usage limits at session mint."""

    def __init__(self, limits: QuotaLimits | None = None, max_concurrent: int | None = None) -> None:
        if limits is not None:
            self.limits = limits
        elif max_concurrent is not None:
            self.limits = QuotaLimits(max_concurrent=max_concurrent)
        else:
            self.limits = QuotaLimits()
        self._active_sessions: dict[str, str] = {}  # session_id -> tenant_id
        self._concurrent_by_tenant: dict[str, int] = {}

    async def check_mint(
        self,
        tenant_id: str,
        current_concurrent: int | None = None,
        current_monthly_minutes: float = 0.0,
    ) -> QuotaCheckResult:
        """Check session mint admission against concurrent and monthly quota limits."""
        concurrent = (
            current_concurrent
            if current_concurrent is not None
            else self._concurrent_by_tenant.get(tenant_id, 0)
        )
        if concurrent >= self.limits.max_concurrent:
            return QuotaCheckResult(
                allowed=False,
                reason=f"Concurrent call limit reached ({self.limits.max_concurrent}).",
            )

        monthly_percent = (
            (current_monthly_minutes / self.limits.max_minutes_month) * 100.0
            if self.limits.max_minutes_month > 0
            else 0.0
        )

        if monthly_percent >= self.limits.hard_cap_percent:
            return QuotaCheckResult(
                allowed=False, reason="Monthly usage hard cap reached (100%)."
            )

        is_warn = monthly_percent >= self.limits.soft_cap_percent
        return QuotaCheckResult(allowed=True, is_soft_cap_warn=is_warn)

    def acquire(self, tenant_id: str, session_id: str) -> None:
        """Track concurrent slot after successful mint."""
        self._active_sessions[session_id] = tenant_id
        self._concurrent_by_tenant[tenant_id] = self._concurrent_by_tenant.get(tenant_id, 0) + 1

    def release(self, session_id: str) -> None:
        """Release concurrent call slot on session end."""
        tenant_id = self._active_sessions.pop(session_id, None)
        if tenant_id is None:
            return
        current = self._concurrent_by_tenant.get(tenant_id, 0)
        self._concurrent_by_tenant[tenant_id] = max(0, current - 1)
