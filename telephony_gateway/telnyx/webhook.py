"""Secure Telnyx webhook admission and legacy event handling."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import ValidationError

from core.transport.caller_id import CallerIdContext
from telephony_gateway.resolver.sip_participant_resolver import SIPParticipantResolver
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
        accepted = await self.event_sink.accept_once(event)
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
    return TelnyxWebhookService(
        public_key=configured_key,
        event_sink=event_sink,
    )


class TelnyxWebhookHandler:
    """Processes incoming Telnyx PSTN webhook events."""

    def __init__(
        self,
        telnyx_public_key: str = "",
        hmac_secret: str = "",
        resolver: SIPParticipantResolver | None = None,
    ) -> None:
        self.public_key = telnyx_public_key
        self.hmac_secret = hmac_secret
        self.resolver = resolver or SIPParticipantResolver()

    def process_event(
        self,
        payload_bytes: bytes,
        payload_json: dict[str, Any],
        signature_header: str | None = None,
        timestamp_header: str | None = None,
    ) -> dict[str, Any]:
        """Process incoming Telnyx webhook payload.

        Fail-closed signature validation.
        """
        if not self.public_key:
            raise ValueError("Telnyx public key required for webhook verification")

        valid = verify_telnyx_signature(
            payload_bytes,
            signature_header,
            timestamp_header,
            public_key=self.public_key,
            hmac_secret=self.hmac_secret,
        )
        if not valid:
            raise ValueError("Invalid Telnyx webhook signature")

        data = payload_json.get("data", {})
        event_type = data.get("event_type", "")
        payload = data.get("payload", {})

        from_num = payload.get("from")
        to_num = payload.get("to")
        if not from_num or not to_num:
            raise ValueError(
                "Webhook payload missing required 'from' or 'to' phone numbers"
            )

        call_id = payload.get("call_control_id", str(uuid4()))

        tenant_id, agent_id = self.resolver.resolve(to_num)

        caller_id = CallerIdContext(
            from_number=from_num,
            to_number=to_num,
            sip_call_id=call_id,
            carrier="telnyx",
        )

        session_id = uuid4()

        return {
            "status": "accepted",
            "event_type": event_type,
            "session_id": session_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "caller_id": caller_id,
            "transport_type": "sip",
        }
