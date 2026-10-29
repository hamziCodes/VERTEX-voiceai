"""Twilio Programmable Voice SIP Adapter Stub."""

from __future__ import annotations

from telephony_gateway.base import BaseTelephonyTransport


class TwilioSIPAdapter(BaseTelephonyTransport):
    """Adapter stub for Twilio SIP Trunking integration."""

    async def connect(self) -> bool:
        self.is_connected = True
        return True

    async def send_audio(self, pcm16_frame: bytes) -> None:
        pass

    async def receive_audio(self) -> bytes | None:
        return None

    async def hangup(self) -> None:
        self.is_connected = False

    async def health_check(self) -> bool:
        return True
