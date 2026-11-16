"""Secure Telnyx webhook admission."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from core.db.repos.telephony_repo import TelephonyAdmissionError
from telephony_gateway.telnyx.models import (
    TelnyxAcceptedEvent,
    TelnyxWebhookEnvelope,
)
from telephony_gateway.telnyx.signature import verify_telnyx_signature


class TelnyxWebhookError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TelnyxEventSink(Protocol):
    async def accept_once(self, event: TelnyxWebhookEnvelope) -> bool: ...


class InMemoryTelnyxEventSink:
    """Deterministic development adapter; Phase 12B supplies PostgreSQL."""

    def __init__(self) -> None:
        self.events: dict[UUID, TelnyxWebhookEnvelope] = {}
        self._lock = asyncio.Lock()

    async def accept_once(self, event: TelnyxWebhookEnvelope) -> bool:
        async with self._lock:
            if event.data.id in self.events:
                return False
            self.events[event.data.id] = event.model_copy(deep=True)
            return True


def _require_ed25519_public_key(value: str) -> None:
    """Fail at startup, not on the first webhook, when the key is unusable.

    A malformed key would otherwise report "verifier configured" while every
    genuine Telnyx webhook fails signature verification.
    """
    import base64
    import binascii

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32:
            raise ValueError
        Ed25519PublicKey.from_public_bytes(raw)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(
            "TELNYX_PUBLIC_KEY must be the base64 Ed25519 public key from the "
            "Telnyx portal."
        ) from exc


class TelnyxWebhookService:
    """Verify exact bytes, validate the envelope, then durably accept once."""

    def __init__(
        self,
        *,
        public_key: str,
        event_sink: TelnyxEventSink,
        now: Callable[[], float] | None = None,
        max_body_bytes: int = 256 * 1024,
        max_drift_sec: float = 300.0,
    ) -> None:
        if not public_key.strip():
            raise ValueError("Telnyx public key is required.")
        _require_ed25519_public_key(public_key.strip())
        if max_body_bytes < 1:
            raise ValueError("max_body_bytes must be positive.")
        self.public_key = public_key.strip()
        self.event_sink = event_sink
        self.now = now
        self.max_body_bytes = max_body_bytes
        self.max_drift_sec = max_drift_sec

    async def accept(
        self,
        raw_body: bytes,
        *,
        signature_header: str | None,
        timestamp_header: str | None,
    ) -> TelnyxAcceptedEvent:
        if not raw_body or len(raw_body) > self.max_body_bytes:
            raise TelnyxWebhookError("invalid_telnyx_event")
        if not verify_telnyx_signature(
            raw_body,
            signature_header,
            timestamp_header,
            public_key=self.public_key,
            max_drift_sec=self.max_drift_sec,
            now=self.now() if self.now is not None else None,
        ):
            raise TelnyxWebhookError("invalid_telnyx_signature")
        try:
            event = TelnyxWebhookEnvelope.model_validate_json(raw_body)
        except (ValidationError, ValueError, UnicodeDecodeError) as exc:
            raise TelnyxWebhookError("invalid_telnyx_event") from exc
        try:
            accepted = await self.event_sink.accept_once(event)
        except TelephonyAdmissionError as exc:
            raise TelnyxWebhookError("telnyx_call_not_admitted") from exc
        return TelnyxAcceptedEvent(
            event_id=event.data.id,
            event_type=event.data.event_type,
            duplicate=not accepted,
        )


def build_telnyx_webhook_service(
    *,
    event_sink: TelnyxEventSink,
    public_key: str | None = None,
) -> TelnyxWebhookService:
    """Build from injected config or the standard secret-safe environment boundary."""
    configured_key = public_key
    if configured_key is None:
        configured_key = os.environ.get("TELNYX_PUBLIC_KEY")
    if not configured_key or not configured_key.strip():
        raise ValueError("TELNYX_PUBLIC_KEY is required for Telnyx webhooks.")
    return TelnyxWebhookService(public_key=configured_key, event_sink=event_sink)
