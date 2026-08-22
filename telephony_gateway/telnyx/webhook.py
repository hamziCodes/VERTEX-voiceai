"""Telnyx Webhook Gateway Handler — Receives Telnyx PSTN webhooks & mints SIP sessions."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from core.transport.caller_id import CallerIdContext
from telephony_gateway.resolver.sip_participant_resolver import SIPParticipantResolver
from telephony_gateway.telnyx.signature import verify_telnyx_signature


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
        if not self.public_key and not self.hmac_secret:
            raise ValueError("Telnyx public key or HMAC secret required for webhook signature verification")

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
            raise ValueError("Webhook payload missing required 'from' or 'to' phone numbers")

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
