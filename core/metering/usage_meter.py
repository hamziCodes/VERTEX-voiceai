"""UCVE Append-Only Usage Metering Engine."""

from __future__ import annotations

from typing import Any

from core.metering.kinds import TEST_CALL_SEC


class UsageMeter:
    """Append-only usage metering engine writing usage events and skipping zero quantities."""

    def __init__(self) -> None:
        self._events_log: list[dict[str, Any]] = []

    def record(
        self, tenant_id: str, session_id: str, kind: str, quantity: float
    ) -> bool:
        """Record usage event if quantity > 0. Returns True if written."""
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

    def record_many(
        self, tenant_id: str, session_id: str, items: dict[str, float]
    ) -> int:
        """Record multiple usage items for session. Returns count of non-zero items recorded."""
        written_count = 0
        for kind, qty in items.items():
            if self.record(tenant_id, session_id, kind, qty):
                written_count += 1

        return written_count
