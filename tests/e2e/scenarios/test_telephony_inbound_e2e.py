from __future__ import annotations

import pytest
from telephony_gateway.base import TelephonyEvent, TelephonyEventType
from telephony_gateway.webhook_normalizer import WebhookNormalizer


def test_telephony_inbound_event_normalization() -> None:
    raw_payload = {
        "data": {
            "event_type": "call.initiated",
            "payload": {
                "from": "+15551234567",
                "to": "+15559876543",
                "call_control_id": "v3:dummy-control-id",
            },
        }
    }

    event = WebhookNormalizer.normalize("telnyx", raw_payload)
    assert isinstance(event, TelephonyEvent)
    assert event.from_number == "+15551234567"
    assert event.to_number == "+15559876543"
    assert event.event_type == TelephonyEventType.CALL_STARTED

