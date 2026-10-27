from __future__ import annotations

import asyncio
import base64
import math
import struct

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from telephony_gateway.adapters.telnyx_media_stream import TelnyxMediaStreamAdapter
from telephony_gateway.telnyx.media import (
    MediaReorderBuffer,
    OrderedMediaPacket,
    TelnyxMediaProtocolError,
    TelnyxMediaState,
    verify_media_websocket_signature,
)
from telephony_gateway.transcoding.mulaw import (
    Pcm16Downsampler16To8,
    Pcm16Upsampler8To16,
    pcm16_to_mulaw,
)
from tests.telephony.fake_telnyx import FakeClock, FakeTelnyxSocket, wait_until

STREAM_URL = "wss://voice.example.test/v1/telnyx/media?token=test-public-fixture"
CALL_CONTROL_ID = "v3:phase12c-call"
STREAM_ID = "32de0dea-53cb-4b21-89a4-9e1819c043bc"
NOW = 1_793_095_200


def _signature() -> tuple[Ed25519PrivateKey, str, str]:
    private_key = Ed25519PrivateKey.generate()
    public_key = base64.b64encode(private_key.public_key().public_bytes_raw()).decode(
        "ascii"
    )
    signature = base64.b64encode(
        private_key.sign(f"{NOW}|{STREAM_URL}".encode())
    ).decode("ascii")
    return private_key, public_key, signature


def _connected() -> dict[str, object]:
    return {"event": "connected", "version": "1.0.0"}


def _start(*, call_control_id: str = CALL_CONTROL_ID) -> dict[str, object]:
    return {
        "event": "start",
        "sequence_number": "1",
        "stream_id": STREAM_ID,
        "start": {
            "call_control_id": call_control_id,
            "call_session_id": "carrier-session-12c",
            "media_format": {
                "encoding": "PCMU",
                "sample_rate": 8000,
                "channels": 1,
            },
        },
    }


def _media(chunk: int, payload: bytes, *, timestamp_ms: int | None = None):
    return {
        "event": "media",
        "sequence_number": str(chunk + 1),
        "stream_id": STREAM_ID,
        "media": {
            "track": "inbound",
            "chunk": str(chunk),
            "timestamp": str(timestamp_ms if timestamp_ms is not None else chunk * 20),
            "payload": base64.b64encode(payload).decode("ascii"),
        },
    }


def _stop() -> dict[str, object]:
    return {
        "event": "stop",
        "sequence_number": "99",
        "stream_id": STREAM_ID,
        "stop": {"call_control_id": CALL_CONTROL_ID},
    }


def _dtmf(digit: str) -> dict[str, object]:
    return {
        "event": "dtmf",
        "sequence_number": "7",
        "stream_id": STREAM_ID,
        "dtmf": {"digit": digit},
    }


def _mark(name: str) -> dict[str, object]:
    return {
        "event": "mark",
        "sequence_number": "8",
        "stream_id": STREAM_ID,
        "mark": {"name": name},
    }


def _tone(sample_rate: int, milliseconds: int, frequency: float = 440.0) -> bytes:
    samples = sample_rate * milliseconds // 1000
    values = [
        int(8000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        for index in range(samples)
    ]
    return struct.pack(f"<{len(values)}h", *values)


def test_media_websocket_signature_covers_exact_url_and_fresh_timestamp() -> None:
    _private, public_key, signature = _signature()

    assert verify_media_websocket_signature(
        stream_url=STREAM_URL,
        signature_header=signature,
        timestamp_header=str(NOW),
        public_key=public_key,
        now=float(NOW),
    )
    assert not verify_media_websocket_signature(
        stream_url=STREAM_URL + "&changed=1",
        signature_header=signature,
        timestamp_header=str(NOW),
        public_key=public_key,
        now=float(NOW),
    )
    assert not verify_media_websocket_signature(
        stream_url=STREAM_URL,
        signature_header=signature,
        timestamp_header=str(NOW - 301),
        public_key=public_key,
        now=float(NOW),
    )


def test_stateful_resampling_conserves_duration_across_fragment_boundaries() -> None:
    pcm8 = _tone(8000, 100)
    upsampler = Pcm16Upsampler8To16()
    upsampled = b"".join(
        upsampler.process(pcm8[start : start + size])
        for start, size in ((0, 158), (158, 442), (600, len(pcm8) - 600))
    )
    assert len(upsampled) == len(pcm8) * 2

    downsampler = Pcm16Downsampler16To8()
    downsampled = b"".join(
        downsampler.process(upsampled[start : start + size])
        for start, size in ((0, 318), (318, 642), (960, len(upsampled) - 960))
    )
    assert len(downsampled) == len(pcm8)


def test_reorder_history_remains_bounded_for_long_calls() -> None:
    reorder = MediaReorderBuffer(window=2, max_loss_fill=10)
    for chunk in range(1, 1001):
        emitted = reorder.add(
            OrderedMediaPacket(
                sequence_number=chunk,
                chunk=chunk,
                timestamp_ms=chunk * 20,
                payload=b"\xff" * 160,
            )
        )
        assert len(emitted) == 1

    assert reorder.tracked_chunk_count <= 32


@pytest.mark.asyncio
async def test_inbound_reorders_deduplicates_fills_loss_and_preserves_metadata() -> (
    None
):
    _private, public_key, signature = _signature()
    clock = FakeClock()
    socket = FakeTelnyxSocket(clock)
    received = []

    async def on_audio(frame) -> None:
        clock.advance(0.001)
        received.append(frame)

    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=on_audio,
        clock=clock.monotonic,
        sleep=clock.sleep,
        reorder_window=1,
        ingress_queue_frames=2,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()

    frame = pcm16_to_mulaw(_tone(8000, 20))
    await socket.feed(_media(2, frame, timestamp_ms=40))
    await socket.feed(_media(1, frame, timestamp_ms=20))
    await socket.feed(_media(2, frame, timestamp_ms=40))
    await socket.feed(_media(4, frame, timestamp_ms=80))
    await socket.feed(_stop())
    await adapter.wait_closed()

    assert [item.chunk for item in received] == [1, 2, 3, 4]
    assert [item.timestamp_ms for item in received] == [20, 40, 60, 80]
    assert [item.synthetic for item in received] == [False, False, True, False]
    assert all(len(item.pcm16) == 640 for item in received)
    assert received[2].pcm16 == b"\x00" * 640
    assert adapter.metrics.duplicate_chunks == 1
    assert adapter.metrics.lost_chunks == 1
    assert adapter.metrics.silence_frames == 1
    assert adapter.metrics.max_ingress_queue_depth <= 2
    assert adapter.metrics.ingress_processing_p95_ms >= 1.0
    assert adapter.state is TelnyxMediaState.CLOSED
    assert adapter.tasks_alive == 0


@pytest.mark.asyncio
async def test_arbitrary_payload_fragmentation_emits_exact_20ms_canonical_frame() -> (
    None
):
    _private, public_key, signature = _signature()
    socket = FakeTelnyxSocket()
    received = []
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=received.append,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()
    encoded = pcm16_to_mulaw(_tone(8000, 20))
    await socket.feed(_media(1, encoded[:37]))
    await socket.feed(_media(2, encoded[37:]))
    await socket.feed(_stop())
    await adapter.wait_closed()

    assert len(received) == 1
    assert len(received[0].pcm16) == 640
    assert adapter.metrics.inbound_payload_bytes == 160


@pytest.mark.asyncio
async def test_egress_is_20ms_paced_bounded_and_clear_discards_queued_audio() -> None:
    _private, public_key, signature = _signature()
    clock = FakeClock()
    socket = FakeTelnyxSocket(clock)
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=lambda _frame: None,
        clock=clock.monotonic,
        sleep=clock.sleep,
        egress_queue_frames=1,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()

    await adapter.send_audio(_tone(16000, 60))
    await wait_until(
        lambda: len([item for _, item in socket.sent if item["event"] == "media"]) == 3
    )
    media = [(at, item) for at, item in socket.sent if item["event"] == "media"]
    assert len(media) == 3
    assert all(
        len(base64.b64decode(item["media"]["payload"])) == 160 for _, item in media
    )
    assert [round(media[i + 1][0] - media[i][0], 3) for i in range(2)] == [0.02, 0.02]
    assert adapter.metrics.max_egress_queue_depth <= 1

    socket.send_gate = asyncio.Event()
    blocked = asyncio.create_task(adapter.send_audio(_tone(16000, 80)))
    await asyncio.sleep(0)
    assert not blocked.done()
    await wait_until(lambda: adapter.egress_inflight)
    clear = asyncio.create_task(adapter.clear_playback())
    await wait_until(lambda: adapter.metrics.cleared_egress_frames >= 1)
    socket.send_gate.set()
    await blocked
    await clear
    assert any(item == {"event": "clear"} for _, item in socket.sent)
    assert adapter.metrics.cleared_egress_frames >= 1

    await socket.feed(_stop())
    await adapter.wait_closed()
    assert adapter.tasks_alive == 0
    assert adapter.metrics.egress_processing_p95_ms >= 0.0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["wrong_call", "bad_codec", "invalid_base64"])
async def test_call_binding_codec_and_media_fail_closed(failure: str) -> None:
    _private, public_key, signature = _signature()
    socket = FakeTelnyxSocket()
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=lambda _frame: None,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    start = _start(call_control_id="wrong") if failure == "wrong_call" else _start()
    if failure == "bad_codec":
        start["start"]["media_format"]["encoding"] = "MP3"
    await socket.feed(start)
    if failure == "invalid_base64":
        await adapter.wait_started()
        invalid = _media(1, b"valid")
        invalid["media"]["payload"] = "%%%not-base64%%%"
        await socket.feed(invalid)

    with pytest.raises(TelnyxMediaProtocolError):
        await adapter.wait_closed()
    assert adapter.state is TelnyxMediaState.ERROR
    assert adapter.tasks_alive == 0


@pytest.mark.asyncio
async def test_dtmf_mark_stop_and_partial_egress_cleanup() -> None:
    _private, public_key, signature = _signature()
    socket = FakeTelnyxSocket()
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=lambda _frame: None,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()

    await adapter.send_audio(_tone(16000, 10))
    await socket.feed(_dtmf("5"))
    await socket.feed(_mark("reply-finished"))
    await socket.feed(_stop())
    await adapter.wait_closed()

    assert adapter.dtmf_events == ["5"]
    assert adapter.marks == ["reply-finished"]
    assert adapter.close_reason == "carrier_stop"
    assert adapter.metrics.discarded_egress_bytes == 320
    assert adapter.metrics.outbound_frames == 0
    assert adapter.tasks_alive == 0


@pytest.mark.asyncio
async def test_unexpected_disconnect_fails_closed_without_task_leaks() -> None:
    _private, public_key, signature = _signature()
    socket = FakeTelnyxSocket()
    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=lambda _frame: None,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()
    await socket.disconnect()

    with pytest.raises(TelnyxMediaProtocolError, match="unexpected_media_disconnect"):
        await adapter.wait_closed()
    assert adapter.state is TelnyxMediaState.ERROR
    assert adapter.close_reason == "unexpected_media_disconnect"
    assert adapter.tasks_alive == 0


@pytest.mark.asyncio
async def test_worker_callback_failure_fails_closed_without_hanging() -> None:
    _private, public_key, signature = _signature()
    socket = FakeTelnyxSocket()

    def fail_callback(_frame) -> None:
        raise RuntimeError("synthetic callback failure")

    adapter = TelnyxMediaStreamAdapter(
        socket=socket,
        expected_stream_url=STREAM_URL,
        expected_call_control_id=CALL_CONTROL_ID,
        public_key=public_key,
        on_audio_frame=fail_callback,
        reorder_window=0,
    )
    await adapter.open(signature_header=signature, timestamp_header=str(NOW), now=NOW)
    await socket.feed(_connected())
    await socket.feed(_start())
    await adapter.wait_started()
    await socket.feed(_media(1, pcm16_to_mulaw(_tone(8000, 20))))

    with pytest.raises(
        TelnyxMediaProtocolError, match="media_worker_failed_RuntimeError"
    ):
        await adapter.wait_closed()
    assert adapter.state is TelnyxMediaState.ERROR
    assert adapter.tasks_alive == 0
