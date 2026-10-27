"""Fail-closed E.164 DID-to-published-agent resolution."""

from __future__ import annotations

from typing import Protocol

from core.db.repos.telephony_repo import DidBinding


class DidRepository(Protocol):
    async def resolve_did(
        self, did_number: str, *, carrier: str = "telnyx"
    ) -> DidBinding: ...


class SIPParticipantResolver:
    """Resolve a carrier-owned number through an explicit durable boundary."""

    def __init__(self, repository: DidRepository) -> None:
        self.repository = repository

    async def resolve(self, did: str, *, carrier: str = "telnyx") -> DidBinding:
        if not _is_e164(did):
            raise ValueError("DID must use normalized E.164 format.")
        return await self.repository.resolve_did(did, carrier=carrier)


def _is_e164(value: str) -> bool:
    return (
        value.startswith("+")
        and 8 <= len(value[1:]) <= 15
        and value[1:].isdigit()
        and value[1] != "0"
    )
