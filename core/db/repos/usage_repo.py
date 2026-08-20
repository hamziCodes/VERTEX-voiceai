"""UCVE Usage & Quotas Append-Only Repository Layer."""

from __future__ import annotations

from core.db.models import QuotaState, UsageEvent


class UsageRepository:
    """Repository managing append-only usage events and quota state tracking."""

    def __init__(self) -> None:
        self._events: list[UsageEvent] = []
        self._quotas: dict[str, QuotaState] = {}

    async def record_usage(self, tenant_id: str, event: UsageEvent) -> UsageEvent:
        """Record append-only usage event."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        if event.tenant_id != tenant_id:
            raise PermissionError("UsageEvent tenant_id mismatch with query context.")

        self._events.append(event)
        return event

    async def list_usage_events(self, tenant_id: str) -> list[UsageEvent]:
        """List usage events for tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        return [e for e in self._events if e.tenant_id == tenant_id]

    async def get_quota_state(self, tenant_id: str) -> QuotaState | None:
        """Retrieve quota state for tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        return self._quotas.get(tenant_id)

    async def update_quota_state(self, tenant_id: str, quota: QuotaState) -> QuotaState:
        """Update quota state for tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        if quota.tenant_id != tenant_id:
            raise PermissionError("QuotaState tenant_id mismatch with query context.")

        self._quotas[tenant_id] = quota
        return quota
