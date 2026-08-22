"""Phase 19: Telephony Abstraction & Secondary Trunk Readiness Test Suite."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from telephony_gateway.adapters.telnyx_direct_sip import TelnyxDirectSIPAdapter
from telephony_gateway.adapters.twilio_media_stream import TwilioMediaStreamTransport
from telephony_gateway.base import BaseTelephonyTransport, TelephonyEvent, TelephonyEventType
from telephony_gateway.failover import TelephonyFailoverRouter, TrunkUnavailableError
from telephony_gateway.trunk_config import SIPTrunkConfig, SIPTrunkProvider, SIPTrunkRole
from telephony_gateway.webhook_normalizer import WebhookNormalizer

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_19_telephony_abstraction_and_secondary_trunk_readiness.md"
    )
    assert plan.is_file()


def test_single_trunk_config_validates() -> None:
    trunk = SIPTrunkConfig(
        provider=SIPTrunkProvider.TELNYX,
        credentials_ref="vault://tenant1/telnyx",
        role=SIPTrunkRole.PRIMARY,
    )
    assert trunk.validate() is True


def test_missing_credentials_fails_closed() -> None:
    trunk = SIPTrunkConfig(
        provider=SIPTrunkProvider.TELNYX,
        credentials_ref="",
    )
    assert trunk.validate() is False


def test_two_trunk_config_validates() -> None:
    t1 = SIPTrunkConfig(
        provider=SIPTrunkProvider.TELNYX,
        credentials_ref="vault://tenant1/telnyx",
        priority=1,
        role=SIPTrunkRole.PRIMARY,
    )
    t2 = SIPTrunkConfig(
        provider=SIPTrunkProvider.TWILIO,
        credentials_ref="vault://tenant1/twilio",
        priority=2,
        role=SIPTrunkRole.SECONDARY,
    )
    router = TelephonyFailoverRouter([t1, t2])
    active = router.get_active_trunk()
    assert active.provider == SIPTrunkProvider.TELNYX


def test_primary_failure_routes_to_secondary() -> None:
    t1 = SIPTrunkConfig(
        provider=SIPTrunkProvider.TELNYX,
        credentials_ref="vault://tenant1/telnyx",
        priority=1,
        role=SIPTrunkRole.PRIMARY,
    )
    t2 = SIPTrunkConfig(
        provider=SIPTrunkProvider.TWILIO,
        credentials_ref="vault://tenant1/twilio",
        priority=2,
        role=SIPTrunkRole.SECONDARY,
    )
    router = TelephonyFailoverRouter([t1, t2])

    # Simulate Primary down
    health_map = {str(t1.trunk_id): False, "telnyx": False}
    active = router.get_active_trunk(health_status_map=health_map)
    assert active.provider == SIPTrunkProvider.TWILIO


def test_single_trunk_primary_failure_surfaces_error() -> None:
    t1 = SIPTrunkConfig(
        provider=SIPTrunkProvider.TELNYX,
        credentials_ref="vault://tenant1/telnyx",
        priority=1,
        role=SIPTrunkRole.PRIMARY,
    )
    router = TelephonyFailoverRouter([t1])

    # Primary down, no secondary
    health_map = {str(t1.trunk_id): False, "telnyx": False}
    with pytest.raises(TrunkUnavailableError) as exc_info:
        router.get_active_trunk(health_status_map=health_map)
    assert "Primary trunk 'telnyx' is down" in str(exc_info.value)


@pytest.mark.asyncio
async def test_telnyx_direct_sip_adapter() -> None:
    adapter = TelnyxDirectSIPAdapter(
        session_id=uuid4(),
        from_number="+15550199000",
        to_number="+18005550199",
    )
    assert isinstance(adapter, BaseTelephonyTransport)
    connected = await adapter.connect()
    assert connected is True
    healthy = await adapter.health_check()
    assert healthy is True
    await adapter.hangup()
    assert adapter.is_connected is False


def test_webhook_normalizer_telnyx_and_twilio() -> None:
    # Telnyx payload
    telnyx_json = {
        "data": {
            "event_type": "call.initiated",
            "payload": {
                "from": "+15550199111",
                "to": "+18005550199",
                "call_control_id": "call-12345",
            },
        }
    }
    ev_t = WebhookNormalizer.normalize("telnyx", telnyx_json)
    assert ev_t.event_type == TelephonyEventType.CALL_STARTED
    assert ev_t.from_number == "+15550199111"
    assert ev_t.payload["carrier"] == "telnyx"

    # Twilio payload
    twilio_json = {
        "CallSid": "CA12345",
        "From": "+15550199222",
        "To": "+18005550199",
        "CallStatus": "in-progress",
    }
    ev_tw = WebhookNormalizer.normalize("twilio", twilio_json)
    assert ev_tw.event_type == TelephonyEventType.CALL_ANSWERED
    assert ev_tw.from_number == "+15550199222"
    assert ev_tw.payload["carrier"] == "twilio"


def test_twilio_media_stream_transport_is_uninstantiable_stub() -> None:
    with pytest.raises(TypeError):
        # Uninstantiable because process_media_event is an abstractmethod
        TwilioMediaStreamTransport(session_id=uuid4(), from_number="+15550123", to_number="+1800555")  # type: ignore
