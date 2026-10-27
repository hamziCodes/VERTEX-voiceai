"""Phase 18: Telephony/SIP Base Integration Test Suite."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from core.transport.caller_id import CallerIdContext
from core.transport.direct_sip import DirectSIPTransport
from core.transport.livekit_sip import LiveKitSIPTransport
from telephony_gateway.resolver.sip_participant_resolver import SIPParticipantResolver
from telephony_gateway.telnyx.signature import verify_telnyx_signature
from telephony_gateway.transcoding.mulaw import mulaw_to_pcm16, pcm16_to_mulaw
from telephony_gateway.transcoding.rebuffer import TelephonyRebuffer
from worker_raw.telephony.inbound_handler import InboundTelephonySessionHandler

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_18_telephony_sip_base_integration.md"
    )
    assert plan.is_file()


def test_mulaw_transcoder_exists() -> None:
    # 160 bytes G.711 μ-law (20ms @ 8kHz) -> 320 bytes PCM16 (20ms @ 8kHz)
    mulaw_input = b"\xff" * 160
    pcm16_output = mulaw_to_pcm16(mulaw_input)
    assert len(pcm16_output) == 320

    # Roundtrip PCM16 -> μ-law -> PCM16
    mulaw_encoded = pcm16_to_mulaw(pcm16_output)
    assert len(mulaw_encoded) == 160


def test_telephony_rebuffer() -> None:
    rebuffer = TelephonyRebuffer(target_samples_per_frame=512)
    # Push 3 x 640-byte 16kHz frames = 1920 bytes (960 samples)
    frames = rebuffer.push(b"\x00" * 1920)
    assert len(frames) == 1  # 1 complete 1024-byte (512-sample) frame
    assert len(frames[0]) == 1024

    # Flush remaining 896 bytes (padded to 1024 bytes)
    flushed = rebuffer.flush()
    assert len(flushed) == 1024


def test_telnyx_signature_verification() -> None:
    import base64

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(private_key.public_key().public_bytes_raw()).decode(
        "ascii"
    )
    payload = b'{"data":{"event_type":"call.initiated"}}'
    ts = "1700000000"
    valid_sig = base64.b64encode(
        private_key.sign(ts.encode("ascii") + b"|" + payload)
    ).decode("ascii")

    assert (
        verify_telnyx_signature(
            payload, valid_sig, ts, public_key=public_key, now=1700000010.0
        )
        is True
    )
    assert (
        verify_telnyx_signature(
            payload, "invalid_signature", ts, public_key=public_key, now=1700000010.0
        )
        is False
    )
    assert (
        verify_telnyx_signature(
            payload, None, ts, public_key=public_key, now=1700000010.0
        )
        is False
    )


def test_sip_participant_resolver() -> None:
    resolver = SIPParticipantResolver()
    tenant_id, agent_id = resolver.resolve("+18005550199")
    assert isinstance(tenant_id, UUID)
    assert isinstance(agent_id, UUID)

    custom_tenant = uuid4()
    custom_agent = uuid4()
    resolver.register_did("+15559998888", custom_tenant, custom_agent)
    res_t, res_a = resolver.resolve("+15559998888")
    assert res_t == custom_tenant
    assert res_a == custom_agent


@pytest.mark.asyncio
async def test_direct_sip_transport_sovereign_pipeline() -> None:
    received_frames: list[bytes] = []

    caller_id = CallerIdContext(from_number="+15550199222", to_number="+18005550199")
    transport = DirectSIPTransport(
        session_id=uuid4(),
        caller_id=caller_id,
        on_audio_frame=lambda frame: received_frames.append(frame),
    )

    # Two 160-byte μ-law frames become 16 kHz PCM16 before rebuffering.
    mulaw_frame = b"\x7f" * 160
    await transport.receive_mulaw_frame(mulaw_frame)
    await transport.receive_mulaw_frame(mulaw_frame)

    assert len(received_frames) >= 1
    assert len(received_frames[0]) == 1024  # 512 samples PCM16 canonical frame
    await transport.close()


def test_caller_id_propagation() -> None:
    caller = CallerIdContext(
        from_number="+15550123456", to_number="+18005550199", carrier="telnyx"
    )
    data = caller.to_dict()
    assert data["from_number"] == "+15550123456"
    assert data["to_number"] == "+18005550199"
    assert data["carrier"] == "telnyx"


@pytest.mark.asyncio
async def test_livekit_optional_adapter_skipped_by_default() -> None:
    caller = CallerIdContext(from_number="+15550123456", to_number="+18005550199")
    lk_adapter = LiveKitSIPTransport(session_id=uuid4(), caller_id=caller)
    assert lk_adapter.enabled is False
    connected = await lk_adapter.connect()
    assert connected is False


@pytest.mark.asyncio
async def test_inbound_telephony_session_handler() -> None:
    session_id = uuid4()
    tenant_id = uuid4()
    agent_id = uuid4()
    caller = CallerIdContext(from_number="+15550123456", to_number="+18005550199")

    handler = InboundTelephonySessionHandler(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        caller_id=caller,
    )

    frames = await handler.handle_inbound_audio(b"\xff" * 160)
    assert isinstance(frames, list)

    duration = await handler.close()
    assert duration >= 0.0
