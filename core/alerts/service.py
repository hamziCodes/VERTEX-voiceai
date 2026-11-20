"""Raise, de-duplicate, notify and resolve operational alerts.

Delivery is honest: a webhook counts as delivered only on a 2xx response;
no channel configured is recorded as ``not_configured``. There is no email
channel (it previously logged "queued" and reported success). Raising an
alert must never break the caller's request path, so callers use
:meth:`AlertService.raise_safely`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx

from core.alerts.models import AlertCode, AlertSeverity, RaisedAlert, sanitize_facts
from core.alerts.repository import AlertRepository, InMemoryAlertRepository
from core.observability.metrics import ucve_alerts_total
from core.runtime.env import is_protected_environment

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "X-Wavia-Alert-Signature"


class AlertWebhookNotifier:
    """POST signed alert JSON to the platform's configured receiver.

    Signature: ``t=<unix seconds>,v1=<hex HMAC-SHA256(secret, "<t>.<body>")>``.
    """

    def __init__(
        self,
        url: str,
        secret: str,
        *,
        timeout_s: float = 5.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc:
            raise ValueError("Alert webhook URL must be an absolute http(s) URL.")
        if is_protected_environment() and parsed.scheme != "https":
            raise ValueError(
                "Alert webhook URL must use https in protected environments."
            )
        if len(secret) < 16:
            raise ValueError("Alert webhook secret must be at least 16 characters.")
        self.url = url
        self._secret = secret.encode("utf-8")
        self._client = httpx.AsyncClient(timeout=timeout_s, transport=transport)

    def sign(self, body: bytes, timestamp: int) -> str:
        digest = hmac.new(
            self._secret, f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        return f"t={timestamp},v1={digest}"

    async def send(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        headers = {
            "Content-Type": "application/json",
            SIGNATURE_HEADER: self.sign(body, int(time.time())),
        }
        try:
            response = await self._client.post(self.url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("alert webhook failed: %s", type(exc).__name__)
            return False
        return 200 <= response.status_code < 300

    async def aclose(self) -> None:
        await self._client.aclose()


def notifier_from_environment() -> AlertWebhookNotifier | None:
    url = (os.environ.get("WAVIA_ALERT_WEBHOOK_URL") or "").strip()
    secret = (os.environ.get("WAVIA_ALERT_WEBHOOK_SECRET") or "").strip()
    if not url:
        return None
    if not secret:
        raise ValueError(
            "WAVIA_ALERT_WEBHOOK_SECRET is required with WAVIA_ALERT_WEBHOOK_URL."
        )
    return AlertWebhookNotifier(url, secret)


class AlertService:
    def __init__(
        self,
        repository: AlertRepository,
        notifier: AlertWebhookNotifier | None = None,
    ) -> None:
        self.repository = repository
        self.notifier = notifier

    async def raise_alert(
        self,
        *,
        alert_key: str,
        code: AlertCode,
        severity: AlertSeverity,
        summary: str,
        tenant_id: UUID | str | None = None,
        facts: dict[str, Any] | None = None,
    ) -> RaisedAlert:
        tenant = UUID(str(tenant_id)) if tenant_id else None
        alert, is_new, escalated = await self.repository.upsert_open(
            alert_key=alert_key[:200],
            code=code,
            severity=severity,
            tenant_id=tenant,
            summary=summary[:300],
            facts=sanitize_facts(facts),
        )
        if not (is_new or escalated):
            return RaisedAlert(alert=alert, is_new=False, delivery="deduplicated")
        ucve_alerts_total.labels(code=code.value, severity=alert.severity.value).inc()
        logger.warning(
            "alert raised code=%s severity=%s key=%s occurrences=%s",
            code.value,
            alert.severity.value,
            alert.alert_key,
            alert.occurrences,
        )
        if self.notifier is None:
            delivery = "not_configured"
        else:
            delivered = await self.notifier.send(
                {"type": "alert.raised", "alert": alert.to_public()}
            )
            delivery = "delivered" if delivered else "failed"
        await self.repository.set_delivery(alert.alert_id, delivery)
        return RaisedAlert(
            alert=alert, is_new=is_new, escalated=escalated, delivery=delivery
        )

    async def raise_safely(self, **kwargs: Any) -> RaisedAlert | None:
        """Raise without ever propagating a failure into the caller."""
        try:
            return await self.raise_alert(**kwargs)
        except Exception as exc:  # noqa: BLE001 - alerting must not break callers
            logger.error("alert could not be recorded: %s", type(exc).__name__)
            return None

    async def resolve(self, alert_key: str, *, resolved_by: str = "system") -> bool:
        try:
            return (
                await self.repository.resolve(alert_key, resolved_by=resolved_by)
                is not None
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("alert could not be resolved: %s", type(exc).__name__)
            return False


def build_alert_service(database: Any | None) -> AlertService:
    """Postgres-backed when a database is open, otherwise in-memory."""
    if database is not None:
        from core.alerts.repository import PostgresAlertRepository

        repository: AlertRepository = PostgresAlertRepository(database)
    else:
        repository = InMemoryAlertRepository()
    return AlertService(repository, notifier_from_environment())


_process_alert_service: AlertService | None = None


def set_process_alert_service(service: AlertService | None) -> None:
    """Register the alert service for code without request context."""
    global _process_alert_service
    _process_alert_service = service


def get_process_alert_service() -> AlertService | None:
    return _process_alert_service
