"""Provider interface for structured post-call summaries."""

from __future__ import annotations

from typing import Protocol

from post_call.models.diarized_turn import DiarizedTurn


class SummaryProvider(Protocol):
    provider_id: str
    model_id: str

    async def summarize_json(self, *, turns: list[DiarizedTurn]) -> object: ...
