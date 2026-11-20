"""Offline WebSocket handshake conformance tests for Phase 05."""

from __future__ import annotations

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from core.protocol.realtime import PROTOCOL_VERSION
from worker_raw.security.ws_policy import WSSecurityPolicy
from worker_raw.ws_session import WebSocketSessionRunner


class _Socket:
    def __init__(self, messages: list[dict[str, object]]) -> None:
        self.messages = list(messages)
        self.closed: tuple[int, str] | None = None

    async def receive(self) -> dict[str, object]:
        return self.messages.pop(0)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = (code, reason)


class _Transport:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    async def send_control_event(
        self, event_type: str, payload: dict[str, object]
    ) -> None:
        self.events.append((str(event_type), payload))


def _runner(socket: _Socket, transport: _Transport) -> WebSocketSessionRunner:
    instance = object.__new__(WebSocketSessionRunner)
    instance.websocket = socket
    instance.transport = transport
    instance.config = SimpleNamespace(session_id="session-1")
    instance._server_sequence = 0
    instance._last_client_sequence = 0
    return instance


@pytest.mark.asyncio
async def test_handshake_accepts_compatible_client_and_returns_range() -> None:
    socket = _Socket(
        [
            {
                "text": json.dumps(
                    {
                        "event_type": "protocol.hello",
                        "protocol_version": PROTOCOL_VERSION,
                        "event_id": "evt-client-1",
                        "sequence": 1,
                        "payload": {
                            "protocol_version": "1.4.0",
                            "sdk": {"name": "test", "version": "1.0.0"},
                        },
                    }
                )
            }
        ]
    )
    transport = _Transport()

    negotiated = await _runner(socket, transport)._perform_protocol_handshake()

    assert negotiated.client_version == "1.4.0"
    assert transport.events[0][0] == "session.ready"
    assert transport.events[0][1]["protocol_version"] == PROTOCOL_VERSION
    assert transport.events[0][1]["supported_range"] == ">=1.0.0 <2.0.0"
    assert socket.closed is None


@pytest.mark.asyncio
async def test_handshake_rejects_incompatible_major_with_typed_error() -> None:
    socket = _Socket(
        [
            {
                "text": json.dumps(
                    {
                        "protocol_version": "2.0.0",
                        "event_id": "evt-future-1",
                        "sequence": 1,
                        "event_type": "protocol.hello",
                        "payload": {
                            "protocol_version": "2.0.0",
                            "sdk": {"name": "future", "version": "2.0.0"},
                        },
                    }
                )
            }
        ]
    )
    transport = _Transport()

    with pytest.raises(Exception, match="PROTOCOL_VERSION_UNSUPPORTED"):
        await _runner(socket, transport)._perform_protocol_handshake()

    assert transport.events[0][0] == "error"
    assert transport.events[0][1]["code"] == "PROTOCOL_VERSION_UNSUPPORTED"
    assert socket.closed == (4406, "protocol version unsupported")


@pytest.mark.asyncio
async def test_handshake_rejects_missing_canonical_envelope() -> None:
    socket = _Socket(
        [
            {
                "text": json.dumps(
                    {
                        "event_type": "protocol.hello",
                        "payload": {
                            "protocol_version": "1.0.0",
                            "sdk": {"name": "legacy", "version": "0.1.0"},
                        },
                    }
                )
            }
        ]
    )
    transport = _Transport()

    with pytest.raises(RuntimeError, match="PROTOCOL_ENVELOPE_REQUIRED"):
        await _runner(socket, transport)._perform_protocol_handshake()

    assert transport.events[0][1]["code"] == "PROTOCOL_ENVELOPE_REQUIRED"
    assert socket.closed == (4400, "protocol envelope required")


@pytest.mark.asyncio
async def test_token_expiry_signals_refresh_then_closes_with_retryable_reason() -> None:
    socket = _Socket([])
    transport = _Transport()
    runner = _runner(socket, transport)
    runner.stop = asyncio.Event()
    runner.token_expires_at = time.time() + 0.05
    runner.token_expiry_notice_sec = 0.03
    runner.token_refresh_url = "/v1/session/refresh"

    await runner._token_expiry_loop()

    assert [kind for kind, _ in transport.events] == [
        "session.token_expiring",
        "session.close",
    ]
    assert transport.events[0][1]["refresh_url"] == "/v1/session/refresh"
    assert transport.events[1][1]["retryable"] is True
    assert socket.closed == (4401, "session token expired")
    assert runner.stop.is_set()


@pytest.mark.asyncio
async def test_remote_session_close_stops_receive_loop_without_retrying() -> None:
    socket = _Socket(
        [
            {
                "text": json.dumps(
                    {
                        "protocol_version": "1.0.0",
                        "event_id": "close-1",
                        "sequence": 1,
                        "event_type": "session.close",
                        "payload": {
                            "code": "CLIENT_DONE",
                            "reason": "user ended session",
                            "retryable": False,
                        },
                    }
                )
            }
        ]
    )
    runner = _runner(socket, _Transport())
    runner.stop = asyncio.Event()
    runner.security_policy = WSSecurityPolicy()

    await runner._receive_loop()

    assert runner.stop.is_set()


@pytest.mark.asyncio
async def test_duplicate_or_out_of_order_client_sequence_is_rejected() -> None:
    socket = _Socket(
        [
            {
                "text": json.dumps(
                    {
                        "protocol_version": "1.0.0",
                        "event_id": "duplicate-1",
                        "sequence": 1,
                        "event_type": "text.turn",
                        "payload": {"text": "must not execute"},
                    }
                )
            }
        ]
    )
    transport = _Transport()
    runner = _runner(socket, transport)
    runner.stop = asyncio.Event()
    runner.security_policy = WSSecurityPolicy()
    runner._last_client_sequence = 1

    await runner._receive_loop()

    assert transport.events[0][0] == "error"
    assert transport.events[0][1]["code"] == "PROTOCOL_SEQUENCE_INVALID"
    assert socket.closed == (4400, "protocol sequence invalid")
    assert runner.stop.is_set()
