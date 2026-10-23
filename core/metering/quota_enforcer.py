"""UCVE Tenant Quota Enforcer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.db.repos.usage_pg import UsageSnapshot, build_usage_repository
from core.metering.quota_limits import QuotaLimits


@dataclass
class QuotaCheckResult:
    """Result of tenant quota admission check."""

    allowed: bool
    reason: str | None = None
    is_soft_cap_warn: bool = False
    max_concurrent: int = 10


class QuotaEnforcer:
    """Quota enforcer checking concurrent and monthly usage limits at session mint."""

    def __init__(
        self,
        limits: QuotaLimits | None = None,
        max_concurrent: int | None = None,
        *,
        repository: Any | None = None,
    ) -> None:
        if limits is not None:
            self.limits = limits
        elif max_concurrent is not None:
            self.limits = QuotaLimits(max_concurrent=max_concurrent)
        else:
            self.limits = QuotaLimits()
        self._active_sessions: dict[str, str] = {}  # session_id -> tenant_id
        self._concurrent_by_tenant: dict[str, int] = {}
        self.repository = (
            repository if repository is not None else build_usage_repository()
        )

    async def check_mint(
        self,
        tenant_id: str,
        current_concurrent: int | None = None,
        current_monthly_minutes: float = 0.0,
    ) -> QuotaCheckResult:
        """Check session mint admission against concurrent and monthly quota limits."""
        snapshot: UsageSnapshot | None = None
        if self.repository is not None:
            snapshot = await self.repository.get_usage_snapshot(tenant_id)

        concurrent = (
            current_concurrent
            if current_concurrent is not None
            else self._concurrent_by_tenant.get(tenant_id, 0)
        )
        max_concurrent = (
            snapshot.max_concurrent if snapshot else self.limits.max_concurrent
        )
        if concurrent >= max_concurrent:
            return QuotaCheckResult(
                allowed=False,
                reason=f"Concurrent call limit reached ({max_concurrent}).",
                max_concurrent=max_concurrent,
            )

        if snapshot:
            seconds_percent = _percent(
                snapshot.monthly_seconds_used, snapshot.monthly_seconds_limit
            )
            token_percent = _percent(
                snapshot.monthly_llm_tokens, snapshot.max_llm_tokens_month
            )
            monthly_percent = max(seconds_percent, token_percent)
            soft_cap_percent = snapshot.soft_cap_percent
            hard_cap_percent = snapshot.hard_cap_percent
        else:
            monthly_percent = _percent(
                current_monthly_minutes, self.limits.max_minutes_month
            )
            soft_cap_percent = self.limits.soft_cap_percent
            hard_cap_percent = self.limits.hard_cap_percent

        if monthly_percent >= hard_cap_percent:
            return QuotaCheckResult(
                allowed=False,
                reason=f"Monthly usage hard cap reached ({hard_cap_percent}%).",
                max_concurrent=max_concurrent,
            )

        is_warn = monthly_percent >= soft_cap_percent
        return QuotaCheckResult(
            allowed=True,
            is_soft_cap_warn=is_warn,
            max_concurrent=max_concurrent,
        )

    def acquire(self, tenant_id: str, session_id: str) -> None:
        """Track concurrent slot after successful mint."""
        self._active_sessions[session_id] = tenant_id
        self._concurrent_by_tenant[tenant_id] = (
            self._concurrent_by_tenant.get(tenant_id, 0) + 1
        )

    def release(self, session_id: str) -> None:
        """Release concurrent call slot on session end."""
        tenant_id = self._active_sessions.pop(session_id, None)
        if tenant_id is None:
            return
        current = self._concurrent_by_tenant.get(tenant_id, 0)
        self._concurrent_by_tenant[tenant_id] = max(0, current - 1)


def _percent(used: float, limit: float) -> float:
    if limit <= 0:
        return 100.0
    return (used / limit) * 100.0
