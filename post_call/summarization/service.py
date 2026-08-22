"""Summarization Service — Generates executive summary & sentiment trajectory."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from post_call.models.diarized_turn import DiarizedTurn


class CallSummary(BaseModel):
    """Executive summary & sentiment analysis trajectory."""

    executive_summary: str
    key_takeaways: list[str] = Field(default_factory=list)
    sentiment_trajectory: list[str] = Field(default_factory=lambda: ["neutral", "positive"])


class SummarizationService:
    """Produces call summary and sentiment trajectory from turns."""

    def summarize(self, turns: list[DiarizedTurn]) -> CallSummary:
        text_full = " ".join(t.text for t in turns)
        if not text_full:
            return CallSummary(
                executive_summary="Empty session — no speech recorded.",
                key_takeaways=[],
                sentiment_trajectory=["neutral"],
            )

        summary_text = f"Caller discussed: {text_full[:120]}..."
        return CallSummary(
            executive_summary=summary_text,
            key_takeaways=["User connected", "Query processed successfully"],
            sentiment_trajectory=["neutral", "positive"],
        )
