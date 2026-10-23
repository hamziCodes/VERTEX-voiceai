"""UCVE Append-Only Usage Metering Engine."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from core.db.models import UsageEvent
from core.db.repos.usage_pg import build_usage_repository
from core.metering.kinds import TEST_CALL_SEC


class UsageMeter:
    """Append-only, idempotent usage metering engine."""

    def __init__(
        self,
        *,
        repository: Any | None = None,
        force_memory: bool = False,
    ) -> None:
        self._events_log: list[dict[str, Any]] = []
        self._event_keys: set[str] = set()
        self.repository = (
            None
            if force_memory
            else repository if repository is not None else build_usage_repository()
        )

    def record(
        self, tenant_id: str, session_id: str, kind: str, quantity: float
    ) -> bool:
        """Record usage event if quantity > 0. Returns True if written."""
        if self.repository is not None:
            raise RuntimeError(
                "Durable usage metering requires await meter.arecord(...)."
            )
        if quantity <= 0:
            return False  # Skip zero or negative quantity (habiba pattern)

        # Skip production quota metering for sandbox test calls
        is_sandbox_test = (kind == TEST_CALL_SEC)

        event = {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "kind": kind,
            "quantity": quantity,
            "is_sandbox": is_sandbox_test,
        }
        self._events_log.append(event)
        return True

    async def arecord(
        self,
        tenant_id: str,
        session_id: str,
        kind: str,
        quantity: float,
        *,
        event_key: str,
        unit: str = "units",
        provider_id: str | None = None,
        provider_request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Persist one retry-safe usage event, or deduplicate it in test mode."""
        if quantity <= 0:
            return False
        event_metadata = dict(metadata or {})
        event_metadata.setdefault("is_sandbox", kind == TEST_CALL_SEC)
        if self.repository is None:
            if event_key in self._event_keys:
                return False
            self._event_keys.add(event_key)
            self._events_log.append(
                {
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "kind": kind,
                    "quantity": quantity,
                    "unit": unit,
                    "provider_id": provider_id,
                    "provider_request_id": provider_request_id,
                    "event_key": event_key,
                    **event_metadata,
                }
            )
            return True
        event = UsageEvent(
            id=str(uuid4()),
            tenant_id=tenant_id,
            session_id=session_id,
            usage_kind=kind,
            quantity=float(quantity),
            event_key=event_key,
            unit=unit,
            provider_id=provider_id,
            provider_request_id=provider_request_id,
            metadata=event_metadata,
            recorded_at=datetime.now(UTC),
        )
        return await self.repository.record_usage(tenant_id, event)

    def record_many(
        self, tenant_id: str, session_id: str, items: dict[str, float]
    ) -> int:
        """Record multiple local usage items and return the number written."""
        written_count = 0
        for kind, qty in items.items():
            if self.record(tenant_id, session_id, kind, qty):
                written_count += 1

        return written_count
