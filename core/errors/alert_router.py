"""Alert Router — Multi-channel operational alert routing (Email & Tenant Webhook v1)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from core.errors.structured import StructuredError

logger = logging.getLogger(__name__)


class AlertRouter:
    """Routes structured errors and quota warnings to alert channels."""

    def __init__(self) -> None:
        self.routed_alerts: list[dict[str, Any]] = []

    async def route_alert(
        self,
        tenant_id: UUID,
        error: StructuredError,
        alert_email: str | None = None,
        alert_webhook_url: str | None = None,
    ) -> bool:
        """Route alert to email and webhook channels based on severity."""
        alert_payload = {
            "tenant_id": tenant_id,
            "code": error.code.value,
            "severity": error.severity,
            "message": error.message,
            "correlation_id": str(error.correlation_id),
        }

        # Severity routing
        if error.severity in ("error", "critical"):
            logger.error("CRITICAL/ERROR Alert for tenant %s: %s", tenant_id, error.message)
            if alert_email:
                # Email dispatch stub
                alert_payload["email_dispatched"] = True

        if alert_webhook_url:
            # Tenant Webhook dispatch stub
            alert_payload["webhook_dispatched"] = True

        self.routed_alerts.append(alert_payload)
        return True
