"""UCVE Native WebSocket Transport Gateway."""

from __future__ import annotations

import json
from typing import Any, Protocol

from control_plane.auth.jwt import verify_session_jwt
from core.observability.logging import get_logger
from core.protocol.realtime import build_event
from core.types.events import ControlEventType

logger = get_logger("ucve.transport.ws")


class WebSocketSender(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...

    async def send_text(self, data: str) -> None: ...

    async def close(self, code: int = 1000, reason: str = "") -> None: ...


class NativeWebSocketTransport:
    """Sovereign WebSocket transport for binary audio and JSON control."""

    def __init__(self, websocket: WebSocketSender | None = None) -> None:
        self._ws = websocket
        self.is_connected: bool = False
        self.session_id: str | None = None
        self.tenant_id: str | None = None
        self.agent_id: str | None = None
        self._sequence = 0

    def bind(self, websocket: WebSocketSender) -> None:
        self._ws = websocket
        self.is_connected = True

    async def connect(self, connection_id: str, token: str) -> bool:
        """Authenticate the JWT from the connection query parameters."""
        try:
            payload = verify_session_jwt(token)
            self.session_id = payload.get("sub")
            self.tenant_id = payload.get("tenant_id")
            self.agent_id = payload.get("agent_id")
            self.is_connected = True
            return True
        except Exception:
            logger.warning("WS authentication failure")
            self.is_connected = False
            return False

    async def send_audio_frame(self, frame_bytes: bytes) -> None:
        """Send 16kHz PCM audio frame to client."""
        if not self.is_connected or self._ws is None:
            raise ConnectionError("WS transport is disconnected.")
        await self._ws.send_bytes(frame_bytes)

    async def send_control_event(
        self, event_type: str | ControlEventType, data: dict[str, Any] | None = None
    ) -> None:
        """Send one canonical versioned JSON control event."""
        if not self.is_connected or self._ws is None:
            raise ConnectionError("WS transport is disconnected.")
        name = (
            event_type.value
            if isinstance(event_type, ControlEventType)
            else event_type
        )
        self._sequence += 1
        await self._ws.send_text(
            json.dumps(build_event(str(name), data, sequence=self._sequence))
        )

    async def close(self, websocket: WebSocketSender | None = None) -> None:
        """Close WebSocket connection and mark transport disconnected."""
        ws = websocket or self._ws
        self.is_connected = False
        if ws is not None:
            try:
                await ws.close(code=1000, reason="session ended")
            except Exception:
                pass
        self._ws = None
