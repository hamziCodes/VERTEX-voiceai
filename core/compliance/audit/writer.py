"""UCVE Audit Event Writer & Callback Dispatcher."""

from __future__ import annotations

from typing import Any, Callable

from core.compliance.audit.actions import AuditAction
from core.compliance.audit.models import AuditEvent
from core.observability.logging import get_logger

logger = get_logger("ucve.audit")

_audit_callbacks: list[Callable[[AuditEvent], None]] = []


def on_audit_event(callback: Callable[[AuditEvent], None]) -> None:
    """Register listener callback for audit events (e.g., SIEM export hook)."""
    _audit_callbacks.append(callback)


class AuditWriter:
    """Audit log writer recording immutable security and compliance events."""

    def __init__(self) -> None:
        self._in_memory_logs: list[AuditEvent] = []

    def record(
        self,
        tenant_id: str,
        action: str | AuditAction,
        resource_type: str,
        resource_id: str,
        actor_id: str = "system",
        actor_type: str = "system",
        detail: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Record audit log event without raising exception to caller on insert failure."""
        try:
            event = AuditEvent(
                tenant_id=tenant_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_id=actor_id,
                actor_type=actor_type,
                detail=detail or {},
                ip=ip,
                user_agent=user_agent,
            )
            self._in_memory_logs.append(event)

            # Dispatch to SIEM / audit listeners
            for callback in _audit_callbacks:
                try:
                    callback(event)
                except Exception as cb_exc:
                    logger.warning("SIEM audit callback exception", error=str(cb_exc))

            return event.id
        except Exception as exc:
            logger.warning("Audit record insert failure (swallowed)", error=str(exc))
            return "failed-audit-insert"
