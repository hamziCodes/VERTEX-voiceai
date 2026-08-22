"""Twilio Media Streams Interface Stub — Abstract & Uninstantiable per Provider-Agnostic Pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod

from telephony_gateway.base import BaseTelephonyTransport


class TwilioMediaStreamTransport(BaseTelephonyTransport, ABC):
    """Abstract interface stub for Twilio Media Streams (WebSocket μ-law stream).

    Intentional abstract stub — not implemented in v1 [LATER]. DirectSIP is sovereign primary.
    """

    @abstractmethod
    async def process_media_event(self, event_data: dict) -> None:
        """Abstract event handler for Twilio WebSocket media frames."""
        pass
