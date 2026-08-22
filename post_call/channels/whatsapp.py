"""WhatsApp Channel Interface Stub — Abstract & Uninstantiable per Spec §3."""

from __future__ import annotations

from abc import ABC, abstractmethod


class WhatsAppDispatcher(ABC):
    """Abstract interface stub for WhatsApp notifications (Green API / Meta WhatsApp Cloud).

    Intentional abstract stub — uninstantiable in v1 [LATER].
    """

    @abstractmethod
    async def send_message(self, recipient_phone: str, template_name: str, parameters: dict) -> None:
        """Abstract notification dispatch interface."""
        pass
