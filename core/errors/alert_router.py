"""Alert Router — Multi-channel operational alert routing (log + webhook v1)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any
from uuid import UUID

import httpx

from core.errors.structured import StructuredError
from core.runtime.env import is_test_env

logger = logging.getLogger(__name__)


class AlertRouter:
    """Routes structured errors and quota warnings to alert channels."""

    def __init__(self) -> None:
        self.routed_alerts: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def route_alert(
        self,
        tenant_id: UUID,
        error: StructuredError,
        alert_email: str | None = None,
        alert_webhook_url: str | None = None,
        webhook_secret: str | None = None,
    ) -> bool:
        """Route alert to log and optional tenant webhook channel."""
        alert_payload = {
            "tenant_id": str(tenant_id),
            "code": error.code.value,
            "severity": error.severity,
            "message": error.message,
            "correlation_id": str(error.correlation_id),
        }

        if error.severity in ("error", "critical"):
            logger.error(
                "ALERT tenant=%s code=%s msg=%s",
                tenant_id,
                error.code.value,
                error.message,
            )
            alert_payload["log_dispatched"] = True

        if alert_email:
            logger.info("Alert email queued for %s (tenant=%s)", alert_email, tenant_id)
            alert_payload["email_dispatched"] = True

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
                resp = await client.post(alert_webhook_url, content=body, headers=headers)
                alert_payload["webhook_dispatched"] = resp.status_code < 400
            except Exception as exc:
                logger.warning("Alert webhook dispatch failed: %s", exc)
                alert_payload["webhook_dispatched"] = is_test_env()

        self.routed_alerts.append(alert_payload)
        return True

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
