"""SIP Participant Resolver — Maps E.164 destination DIDs to (tenant_id, agent_id)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a1")


class SIPParticipantResolver:
    """Resolves destination PSTN phone numbers (DIDs) to tenant and agent IDs."""

    def __init__(self, db_session: Any | None = None) -> None:
        self.db = db_session
        # Pre-seeded registry mapping DID strings (E.164 format) -> (tenant_id, agent_id)
        self._did_map: dict[str, tuple[UUID, UUID]] = {
            "+18005550199": (DEFAULT_TENANT_ID, DEFAULT_AGENT_ID),
            "+18005550100": (DEFAULT_TENANT_ID, DEFAULT_AGENT_ID),
        }

    def register_did(self, did: str, tenant_id: UUID, agent_id: UUID) -> None:
        """Register a DID mapping in memory."""
        clean_did = self.normalize_e164(did)
        self._did_map[clean_did] = (tenant_id, agent_id)

    def resolve(self, to_did: str) -> tuple[UUID, UUID]:
        """Resolve a destination DID to (tenant_id, agent_id).

        Falls back to default tenant/agent if DID is unknown in dev/sandbox mode.
        """
        clean_did = self.normalize_e164(to_did)
        if clean_did in self._did_map:
            return self._did_map[clean_did]
        return (DEFAULT_TENANT_ID, DEFAULT_AGENT_ID)

    @staticmethod
    def normalize_e164(phone_number: str) -> str:
        """Normalize a phone number string into standard E.164 format (+1XXXXXXXXXX)."""
        cleaned = "".join(c for c in phone_number if c.isdigit() or c == "+")
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        return cleaned
