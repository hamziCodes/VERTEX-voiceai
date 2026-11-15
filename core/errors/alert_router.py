"""Legacy per-error alert router (log + optional webhook).

Superseded by :mod:`core.alerts` (durable, de-duplicated alerts with signed
delivery). Kept for existing callers; Phase 14 removed its fake successes:
there is no email channel, a failed webhook is reported as failed in every
environment, and the routed-alert history is bounded. Classified
delete-proposed in the Phase 14 cleanup report.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections import deque
from typing import Any
from uuid import UUID

import httpx

from core.errors.structured import StructuredError

logger = logging.getLogger(__name__)


class AlertRouter:
    """Routes structured errors and quota warnings to alert channels."""

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.routed_alerts: deque[dict[str, Any]] = deque(maxlen=100)
        self._client: httpx.AsyncClient | None = None
        self._transport = transport

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0, transport=self._transport)
        return self._client

    async def route_alert(
        self,
        tenant_id: UUID,
        error: StructuredError,
        alert_email: str | None = None,
        alert_webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> bool:
        """Route to log and optional webhook; True only if every channel succeeded."""
        alert_payload: dict[str, Any] = {
            "tenant_id": str(tenant_id),
            "code": error.code.value,
            "severity": error.severity,
            "message": error.message,
            "correlation_id": str(error.correlation_id),
        }

        if error.severity in ("error", "critical"):
            # Message text may carry user content; log the code only.
            logger.error("ALERT tenant=%s code=%s", tenant_id, error.code.value)
            alert_payload["log_dispatched"] = True

        delivered = True
        if alert_email:
            # No email channel exists. Never report an email as sent.
            logger.warning("Alert email requested but no email channel exists.")
            alert_payload["email_dispatched"] = False
            delivered = False

        if alert_webhook_url:
            body = json.dumps(alert_payload).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if webhook_secret:
                sig = hmac.new(
                    webhook_secret.encode("utf-8"), body, hashlib.sha256
                ).hexdigest()
                headers["X-UCVE-Alert-Signature"] = sig
            try:
                client = self._get_client()
                resp = await client.post(
                    alert_webhook_url, content=body, headers=headers
                )
                alert_payload["webhook_dispatched"] = 200 <= resp.status_code < 300
            except Exception as exc:
                logger.warning("Alert webhook dispatch failed: %s", type(exc).__name__)
                alert_payload["webhook_dispatched"] = False
            delivered = delivered and bool(alert_payload["webhook_dispatched"])

        self.routed_alerts.append(alert_payload)
        return delivered

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
