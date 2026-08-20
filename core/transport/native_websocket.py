"""UCVE Native WebSocket Transport Gateway."""

from __future__ import annotations

import time
from typing import Any, Protocol

from control_plane.auth.jwt import verify_session_jwt
from core.observability.logging import get_logger
from core.types.events import ControlEvent, ControlEventType

logger = get_logger("ucve.transport.ws")


class WebSocketSender(Protocol):
    async def send_bytes(self, data: bytes) -> None: ...

    async def send_text(self, data: str) -> None: ...


class NativeWebSocketTransport:
    """Sovereign plane native WebSocket transport handling binary audio & control messages."""

    def __init__(self, websocket: WebSocketSender | None = None) -> None:
        self._ws = websocket
        self.is_connected: bool = False
        self.session_id: str | None = None
        self.tenant_id: str | None = None
        self.agent_id: str | None = None

    def bind(self, websocket: WebSocketSender) -> None:
        self._ws = websocket

    async def connect(self, connection_id: str, token: str) -> bool:
        """Authenticate JWT token (from ?token= query param) and accept WS connection."""
        try:
            payload = verify_session_jwt(token)
            self.session_id = payload.get("sub")
            self.tenant_id = payload.get("tenant_id")
            self.agent_id = payload.get("agent_id")
            self.is_connected = True
            return True
        except Exception as exc:
            logger.warning("WS authentication failure", error=str(exc))
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
        """Send JSON control event (control.pong, control.metric, language_changed, barge_in)."""
        if not self.is_connected or self._ws is None:
            raise ConnectionError("WS transport is disconnected.")
        if isinstance(event_type, ControlEventType):
            evt = ControlEvent(
                event_type=event_type,
                timestamp_ms=time.time() * 1000.0,
                payload=data or {},
            )
        else:
            try:
                typed = ControlEventType(event_type)
            except ValueError:
                # Allow ping and aliased names not in enum yet
                import json

                await self._ws.send_text(
                    json.dumps(
                        {
                            "event_type": event_type,
                            "timestamp_ms": time.time() * 1000.0,
                            "payload": data or {},
                        }
                    )
                )
                return
            evt = ControlEvent(
                event_type=typed,
                timestamp_ms=time.time() * 1000.0,
                payload=data or {},
            )
        await self._ws.send_text(evt.to_json())

    async def close(self) -> None:
        """Close WebSocket connection."""
        self.is_connected = False
        self._ws = None
