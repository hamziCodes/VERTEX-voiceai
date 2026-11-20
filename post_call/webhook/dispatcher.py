"""Bounded, signed, response-body-free webhook transport."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from post_call.webhook.models import TenantWebhookTarget, WebhookDelivery
from post_call.webhook.policy import WebhookEndpointPolicy, WebhookSecurityError

SecretResolver = Callable[[str, str], str | Awaitable[str]]


class VaultWebhookSecretResolver:
    """Resolve tenant webhook signing keys through the encrypted secret vault."""

    def __init__(self, vault: object) -> None:
        self.vault = vault

    async def __call__(self, tenant_id: str, credential_ref: str) -> str:
        resolver = getattr(self.vault, "aresolve_credential", None)
        if resolver is None:
            raise RuntimeError("Async secret resolution is unavailable.")
        resolved = await resolver(
            tenant_id,
            "webhook",
            credential_ref=credential_ref,
            credential_type="hmac_secret",
            tier="byok",
        )
        return str(resolved.secret)


@dataclass(frozen=True, slots=True)
class WebhookAttemptResult:
    succeeded: bool
    retryable: bool
    duration_ms: int
    status_code: int | None = None
    error_code: str | None = None


class WebhookDispatcher:
    def __init__(
        self,
        *,
        secret_resolver: SecretResolver,
        client: httpx.AsyncClient | None = None,
        endpoint_policy: WebhookEndpointPolicy | None = None,
        connect_timeout_seconds: float = 1.0,
        read_timeout_seconds: float = 3.0,
        total_timeout_seconds: float = 5.0,
        max_payload_bytes: int = 256 * 1024,
    ) -> None:
        if not 0 < connect_timeout_seconds <= 3.0:
            raise ValueError("Webhook connect timeout must be between 0 and 3 seconds.")
        if not 0 < read_timeout_seconds <= 5.0:
            raise ValueError("Webhook read timeout must be between 0 and 5 seconds.")
        if not 0 < total_timeout_seconds <= 8.0:
            raise ValueError("Webhook total timeout must be between 0 and 8 seconds.")
        if not 1_024 <= max_payload_bytes <= 1024 * 1024:
            raise ValueError("Webhook payload limit must be between 1 KiB and 1 MiB.")
        self.secret_resolver = secret_resolver
        self.endpoint_policy = endpoint_policy or WebhookEndpointPolicy()
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.total_timeout_seconds = total_timeout_seconds
        self.max_payload_bytes = max_payload_bytes
        self._client = client or httpx.AsyncClient(follow_redirects=False)
        self._owns_client = client is None

    @staticmethod
    def canonical_payload(payload: dict[str, object]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    @staticmethod
    def compute_signature(payload_bytes: bytes, secret: str) -> str:
        if not secret:
            raise ValueError("Webhook signing secret is required.")
        return hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

    async def send_once(
        self,
        target: TenantWebhookTarget,
        delivery: WebhookDelivery,
    ) -> WebhookAttemptResult:
        started = time.perf_counter()

        def result(
            *,
            succeeded: bool,
            retryable: bool,
            status_code: int | None = None,
            error_code: str | None = None,
        ) -> WebhookAttemptResult:
            return WebhookAttemptResult(
                succeeded=succeeded,
                retryable=retryable,
                status_code=status_code,
                error_code=error_code,
                duration_ms=max(0, round((time.perf_counter() - started) * 1000)),
            )

        try:
            await self.endpoint_policy.validate(
                target.url,
                expected_addresses=frozenset(target.approved_addresses),
            )
        except WebhookSecurityError:
            return result(
                succeeded=False,
                retryable=False,
                error_code="endpoint_blocked",
            )
        try:
            pending_secret = self.secret_resolver(
                str(target.tenant_id), target.credential_ref
            )
            secret = (
                await pending_secret
                if inspect.isawaitable(pending_secret)
                else pending_secret
            )
            if not secret:
                raise ValueError("empty secret")
        except Exception:
            return result(
                succeeded=False,
                retryable=False,
                error_code="credential_unavailable",
            )
        try:
            payload_bytes = self.canonical_payload(delivery.payload)
        except (TypeError, ValueError):
            return result(
                succeeded=False,
                retryable=False,
                error_code="payload_invalid",
            )
        if len(payload_bytes) > self.max_payload_bytes:
            return result(
                succeeded=False,
                retryable=False,
                error_code="payload_too_large",
            )
        headers = {
            "Content-Type": "application/json",
            "X-Idempotency-Key": delivery.idempotency_key,
            "X-Wavia-Event": delivery.event_type,
            "X-Wavia-Signature": self.compute_signature(payload_bytes, secret),
        }
        timeout = httpx.Timeout(
            connect=self.connect_timeout_seconds,
            read=self.read_timeout_seconds,
            write=self.read_timeout_seconds,
            pool=self.connect_timeout_seconds,
        )
        try:
            async with asyncio.timeout(self.total_timeout_seconds):
                async with self._client.stream(
                    "POST",
                    target.url,
                    content=payload_bytes,
                    headers=headers,
                    timeout=timeout,
                    follow_redirects=False,
                ) as response:
                    status = response.status_code
        except (TimeoutError, httpx.TimeoutException):
            return result(
                succeeded=False,
                retryable=True,
                error_code="delivery_timeout",
            )
        except httpx.HTTPError:
            return result(
                succeeded=False,
                retryable=True,
                error_code="network_error",
            )
        if 200 <= status < 300:
            return result(succeeded=True, retryable=False, status_code=status)
        if 300 <= status < 400:
            return result(
                succeeded=False,
                retryable=False,
                status_code=status,
                error_code="redirect_blocked",
            )
        if status in {408, 425, 429} or 500 <= status < 600:
            return result(
                succeeded=False,
                retryable=True,
                status_code=status,
                error_code="remote_unavailable",
            )
        return result(
            succeeded=False,
            retryable=False,
            status_code=status,
            error_code="remote_rejected",
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
