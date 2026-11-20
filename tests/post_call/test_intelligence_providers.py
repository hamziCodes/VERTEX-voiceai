"""Stage 3: post-call intelligence has a real provider (and an honest mock)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest

from core.providers.interfaces.llm import LLMStreamChunk
from post_call.extraction.schema import ExtractionField, TenantExtractionSchema
from post_call.extraction.service import ExtractionService, IntelligenceOutputError
from post_call.intelligence_providers import (
    LLMIntelligenceProvider,
    MockIntelligenceProvider,
    build_post_call_providers,
)
from post_call.models.diarized_turn import DiarizedTurn
from post_call.summarization.service import SummarizationService

TURNS = [
    DiarizedTurn(speaker="user", text="Hi, can I book a cleaning for Tuesday?", start_ms=0, end_ms=2000),
    DiarizedTurn(speaker="agent", text="Yes, Tuesday at 10 AM is free.", start_ms=2100, end_ms=4000),
    DiarizedTurn(speaker="user", text="Great, my name is Sara Khan.", start_ms=4100, end_ms=6000),
]


class _ScriptedLLM:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, Any]] = []

    async def generate_stream(self, messages: list[dict[str, Any]], config: Any, cancellation_token: Any = None) -> AsyncIterator[LLMStreamChunk]:
        self.messages = messages
        for index in range(0, len(self.reply), 7):
            yield LLMStreamChunk(text=self.reply[index : index + 7])


@pytest.mark.asyncio
async def test_llm_summary_is_validated_against_the_transcript() -> None:
    reply = (
        '```json\n{"executive_summary": "Caller booked a Tuesday cleaning.",'
        ' "key_takeaways": ["Tuesday 10 AM"], "sentiment_trajectory": ["satisfied"],'
        ' "evidence": [{"turn_id": 0, "quote": "book a cleaning for Tuesday"}]}\n```'
    )
    llm = _ScriptedLLM(reply)
    provider = LLMIntelligenceProvider(llm, provider_id="groq", model_id="openai/gpt-oss-120b")

    summary = await SummarizationService(provider).summarize(TURNS)

    assert summary is not None
    assert summary.executive_summary == "Caller booked a Tuesday cleaning."
    assert summary.source_turn_ids == (0,)
    assert (summary.provider_id, summary.model_id) == ("groq", "openai/gpt-oss-120b")
    assert "[0] user: Hi, can I book a cleaning for Tuesday?" in llm.messages[1]["content"]


@pytest.mark.asyncio
async def test_invented_evidence_is_rejected() -> None:
    reply = '{"executive_summary": "x", "evidence": [{"turn_id": 1, "quote": "we are closed"}]}'
    provider = LLMIntelligenceProvider(_ScriptedLLM(reply), provider_id="groq", model_id="m")
    with pytest.raises(IntelligenceOutputError):
        await SummarizationService(provider).summarize(TURNS)


@pytest.mark.asyncio
async def test_llm_extraction_returns_evidenced_fields() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[ExtractionField(name="caller_name", description="Full name of the caller")],
    )
    reply = (
        '{"fields": {"caller_name": {"value": "Sara Khan", "confidence": 0.95,'
        ' "evidence": [{"turn_id": 2, "quote": "my name is Sara Khan"}]}}}'
    )
    provider = LLMIntelligenceProvider(_ScriptedLLM(reply), provider_id="groq", model_id="m")

    result = await ExtractionService(provider).extract(TURNS, schema, "standard")

    assert result.fields["caller_name"].value == "Sara Khan"
    assert result.fields["caller_name"].source_turn_ids == (2,)


@pytest.mark.asyncio
async def test_mock_provider_is_labelled_and_quotes_the_real_transcript() -> None:
    mock = MockIntelligenceProvider()
    summary = await SummarizationService(mock).summarize(TURNS)
    assert summary is not None
    assert summary.provider_id == "mock"
    assert summary.executive_summary.startswith("Mock summary (no model was called).")
    assert "book a cleaning for Tuesday" in summary.executive_summary

    schema = TenantExtractionSchema(tenant_id=uuid4(), fields=[ExtractionField(name="caller_name")])
    extraction = await ExtractionService(mock).extract(TURNS, schema, "standard")
    assert extraction.fields["caller_name"].value is None
    assert extraction.fields["caller_name"].confidence == 0.0


def test_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("RUN_LIVE_PROVIDERS", "RUN_MOCK_PROVIDERS", "PLATFORM_GROQ_API_KEY", "WAVIA_POST_CALL_LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("UCVE_ENV", "development")
    extraction, summary = build_post_call_providers()  # type: ignore[misc]
    assert extraction.provider_id == summary.provider_id == "mock"

    monkeypatch.setenv("UCVE_ENV", "production")
    assert build_post_call_providers() is None  # live mode, no platform key: disabled

    monkeypatch.setenv("PLATFORM_GROQ_API_KEY", "test-not-a-real-key")
    extraction, summary = build_post_call_providers()  # type: ignore[misc]
    assert isinstance(summary, LLMIntelligenceProvider)
    assert summary.provider_id == "groq"

    monkeypatch.setenv("WAVIA_POST_CALL_LLM_PROVIDER", "whisper")
    assert build_post_call_providers() is None
