"""Strict, evidence-backed post-call summarization."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from post_call.extraction.service import (
    EvidenceRef,
    IntelligenceOutputError,
    IntelligenceProviderUnavailableError,
    evidence_turn_ids,
    parse_provider_json,
)
from post_call.models.diarized_turn import DiarizedTurn
from post_call.summarization.provider import SummaryProvider


class _RawSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=1, max_length=2_000)
    key_takeaways: tuple[str, ...] = Field(default=(), max_length=20)
    sentiment_trajectory: tuple[str, ...] = Field(default=(), max_length=50)
    evidence: tuple[EvidenceRef, ...]


class CallSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    executive_summary: str
    key_takeaways: tuple[str, ...] = ()
    sentiment_trajectory: tuple[str, ...] = ()
    source_turn_ids: tuple[int, ...]
    provider_id: str
    model_id: str


class SummarizationService:
    def __init__(self, provider: SummaryProvider | None = None) -> None:
        self.provider = provider

    async def summarize(self, turns: list[DiarizedTurn]) -> CallSummary | None:
        if not turns or not any(turn.text.strip() for turn in turns):
            return None
        if self.provider is None:
            raise IntelligenceProviderUnavailableError(
                "A structured summary provider is required."
            )
        try:
            raw = await self.provider.summarize_json(turns=turns)
            parsed = _RawSummary.model_validate(parse_provider_json(raw))
            source_ids = evidence_turn_ids(parsed.evidence, turns)
        except IntelligenceOutputError:
            raise
        except (ValidationError, TypeError, ValueError) as exc:
            raise IntelligenceOutputError(
                "Provider summary failed schema validation."
            ) from exc
        if not source_ids:
            raise IntelligenceOutputError("Summary requires transcript evidence.")
        return CallSummary(
            executive_summary=parsed.executive_summary,
            key_takeaways=parsed.key_takeaways,
            sentiment_trajectory=parsed.sentiment_trajectory,
            source_turn_ids=source_ids,
            provider_id=self.provider.provider_id,
            model_id=self.provider.model_id,
        )
