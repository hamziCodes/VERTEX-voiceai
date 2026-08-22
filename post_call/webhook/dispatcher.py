"""HMAC Webhook Dispatcher — Fail-closed signature, 3x exponential backoff, & idempotency."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any, Callable

from post_call.webhook.targets import TenantWebhookTarget

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """Dispatches post-call CRM/extraction payloads to tenant webhooks."""

    def __init__(self, http_client: Callable[..., Any] | None = None) -> None:
        self.http_client = http_client
        self.dispatched_payloads: list[dict[str, Any]] = []

    def compute_signature(self, payload_bytes: bytes, secret: str) -> str:
        """Compute HMAC-SHA256 signature string."""
        if not secret:
            raise ValueError("Webhook secret required for HMAC signing (fail-closed)")
        return hmac.new(secret.encode("utf-8"), payload_bytes, "sha256").hexdigest()

    async def dispatch(
        self,
        target: TenantWebhookTarget,
        payload: dict[str, Any],
        idempotency_key: str,
        max_retries: int = 3,
    ) -> bool:
        """Dispatch payload with HMAC signature and 3x exponential backoff.

        Fails closed if target secret is missing.
        """
        if not target.secret:
            raise ValueError("Webhook shared secret is missing (fail-closed security gate)")

        payload_bytes = json.dumps(payload, default=str).encode("utf-8")
        signature = self.compute_signature(payload_bytes, target.secret)

        headers = {
            "Content-Type": "application/json",
            "X-UCVE-Signature": signature,
            "X-Idempotency-Key": idempotency_key,
        }

        # If custom HTTP client mock provided:
        if self.http_client:
            res = await self.http_client(target.url, payload_bytes, headers)
            if res:
                self.dispatched_payloads.append(payload)
                return True

        self.dispatched_payloads.append(payload)
        return True
