"""Provider interface for structured post-call extraction."""

from __future__ import annotations

from typing import Protocol

from post_call.extraction.schema import TenantExtractionSchema
from post_call.models.diarized_turn import DiarizedTurn


class ExtractionProvider(Protocol):
    provider_id: str
    model_id: str

    async def extract_json(
        self, *, turns: list[DiarizedTurn], schema: TenantExtractionSchema
    ) -> object: ...
