"""Provider-neutral Webhook Normalizer — Maps Telnyx & Twilio webhook payloads to TelephonyEvent."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

from telephony_gateway.base import TelephonyEvent, TelephonyEventType


class WebhookNormalizer:
    """Normalizes carrier-specific webhook events into unified TelephonyEvent instances."""

    @staticmethod
    def normalize(provider: str, payload_json: dict[str, Any]) -> TelephonyEvent:
        """Parse provider payload (telnyx / twilio) into canonical TelephonyEvent."""
        prov = provider.lower().strip()

        if prov == "telnyx":
            data = payload_json.get("data", {})
            raw_event = data.get("event_type", "")
            data_payload = data.get("payload", {})

            from_num = data_payload.get("from", "")
            to_num = data_payload.get("to", "")
            call_id_str = data_payload.get("call_control_id", str(uuid4()))

            event_kind = TelephonyEventType.CALL_STARTED
            if "answered" in raw_event:
                event_kind = TelephonyEventType.CALL_ANSWERED
            elif "hangup" in raw_event or "ended" in raw_event:
                event_kind = TelephonyEventType.CALL_ENDED
            elif "dtmf" in raw_event:
                event_kind = TelephonyEventType.DTMF

            return TelephonyEvent(
                event_type=event_kind,
                session_id=uuid4(),
                from_number=from_num,
                to_number=to_num,
                timestamp_ms=int(time.time() * 1000),
                payload={"carrier": "telnyx", "call_control_id": call_id_str, "raw": raw_event},
            )

        elif prov == "twilio":
            call_sid = payload_json.get("CallSid", str(uuid4()))
            from_num = payload_json.get("From", "")
            to_num = payload_json.get("To", "")
            call_status = payload_json.get("CallStatus", "").lower()

            event_kind = TelephonyEventType.CALL_STARTED
            if call_status in ("in-progress", "answered"):
                event_kind = TelephonyEventType.CALL_ANSWERED
            elif call_status in ("completed", "canceled", "failed", "busy"):
                event_kind = TelephonyEventType.CALL_ENDED

            return TelephonyEvent(
                event_type=event_kind,
                session_id=uuid4(),
                from_number=from_num,
                to_number=to_num,
                timestamp_ms=int(time.time() * 1000),
                payload={"carrier": "twilio", "call_sid": call_sid, "raw_status": call_status},
            )

        else:
            raise ValueError(f"Unsupported telephony webhook provider: '{provider}'")
