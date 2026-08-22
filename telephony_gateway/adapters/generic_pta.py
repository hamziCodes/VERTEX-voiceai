"""Generic Private Telephony Appliance (PTA) Adapter Stub."""

from __future__ import annotations

from uuid import UUID

from telephony_gateway.base import BaseTelephonyTransport


class GenericPTAAdapter(BaseTelephonyTransport):
    """Adapter stub for generic enterprise Private Telephony Appliances (Cisco, Avaya, Asterisk)."""

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
