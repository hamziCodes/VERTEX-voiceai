"""Concrete post-call intelligence providers (summary + structured extraction).

``LLMIntelligenceProvider`` asks a catalogued LLM for strict JSON with
verbatim evidence quotes; ``SummarizationService`` / ``ExtractionService``
then reject anything that is not valid JSON or whose quotes are not in the
transcript, so a model cannot invent evidence.

``MockIntelligenceProvider`` exists only for mock provider mode (development
and tests, never a protected environment). It is labelled ``provider_id =
"mock"`` everywhere it is stored and shown, builds its summary from real
transcript quotes, and extracts nothing (every field null, confidence 0).
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from typing import Any

from core.providers.interfaces.llm import LLMConfig
from core.providers.mode import provider_runtime_status
from core.runtime.env import is_protected_environment
from post_call.extraction.schema import TenantExtractionSchema
from post_call.models.diarized_turn import DiarizedTurn

_MAX_TRANSCRIPT_CHARS = 24_000

_SUMMARY_INSTRUCTIONS = """You summarise a completed phone or web call for the business that ran it.
Return ONLY a JSON object, no prose, with exactly these keys:
{"executive_summary": string (<= 600 characters),
 "key_takeaways": [string, ...] (<= 5 items),
 "sentiment_trajectory": [string, ...] (e.g. "neutral", "frustrated", "satisfied"; <= 5),
 "evidence": [{"turn_id": integer, "quote": string}, ...] (1-5 items)}
Every evidence quote MUST be copied verbatim from the turn with that turn_id.
Use only what is in the transcript. Never add facts."""

_EXTRACTION_INSTRUCTIONS = """You extract structured fields from a completed call transcript.
Return ONLY a JSON object, no prose: {"fields": {"<field name>": {"value": ..., "confidence": number 0-1,
"evidence": [{"turn_id": integer, "quote": string}, ...]}, ...}} with one entry per requested field.
If a field is not stated in the transcript, use {"value": null, "confidence": 0, "evidence": []}.
Every evidence quote MUST be copied verbatim from the turn with that turn_id. Never guess."""


def _transcript(turns: Sequence[DiarizedTurn]) -> str:
    lines = [
        f"[{index}] {turn.speaker}: {turn.text}" for index, turn in enumerate(turns)
    ]
    text = "\n".join(lines)
    return text[-_MAX_TRANSCRIPT_CHARS:]


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    return cleaned.strip()


class LLMIntelligenceProvider:
    """Summary and extraction through one catalogued LLM provider."""

    def __init__(
        self, llm: Any, *, provider_id: str, model_id: str, max_tokens: int = 900
    ) -> None:
        self._llm = llm
        self.provider_id = provider_id
        self.model_id = model_id
        self._config = LLMConfig(model=model_id, temperature=0.0, max_tokens=max_tokens)

    async def _complete(self, system: str, user: str) -> str:
        parts: list[str] = []
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        async for chunk in self._llm.generate_stream(messages, self._config):
            if chunk.text:
                parts.append(chunk.text)
        return _strip_fences("".join(parts))

    async def summarize_json(self, *, turns: list[DiarizedTurn]) -> object:
        return await self._complete(
            _SUMMARY_INSTRUCTIONS, "Transcript:\n" + _transcript(turns)
        )

    async def extract_json(
        self, *, turns: list[DiarizedTurn], schema: TenantExtractionSchema
    ) -> object:
        fields = [
            {"name": field.name, "type": field.type, "description": field.description}
            for field in schema.fields
        ]
        user = (
            "Fields:\n"
            + json.dumps(fields, ensure_ascii=False)
            + "\n\nTranscript:\n"
            + _transcript(turns)
        )
        return await self._complete(_EXTRACTION_INSTRUCTIONS, user)

    async def aclose(self) -> None:
        close = getattr(self._llm, "aclose", None)
        if close is not None:
            await close()


class MockIntelligenceProvider:
    """Deterministic, explicitly labelled provider for mock provider mode."""

    provider_id = "mock"
    model_id = "mock-transcript-quotes"

    async def summarize_json(self, *, turns: list[DiarizedTurn]) -> object:
        spoken = [
            (index, turn) for index, turn in enumerate(turns) if turn.text.strip()
        ]
        caller = [
            (index, turn)
            for index, turn in spoken
            if turn.speaker.lower() in {"user", "caller"}
        ]
        quoted = (caller or spoken)[:3]
        first = quoted[0][1].text.strip() if quoted else ""
        return {
            "executive_summary": f'Mock summary (no model was called). The caller said: "{first[:200]}"',
            "key_takeaways": [
                f"{turn.speaker}: {turn.text.strip()[:120]}" for _, turn in quoted
            ],
            "sentiment_trajectory": [],
            "evidence": [
                {"turn_id": index, "quote": turn.text.strip()[:200]}
                for index, turn in quoted
            ],
        }

    async def extract_json(
        self, *, turns: list[DiarizedTurn], schema: TenantExtractionSchema
    ) -> object:
        return {
            "fields": {
                field.name: {"value": None, "confidence": 0.0, "evidence": []}
                for field in schema.fields
            }
        }


def build_post_call_providers() -> tuple[Any, Any] | None:
    """Return ``(extraction, summary)`` providers, or ``None`` when unavailable.

    Mock provider mode uses the labelled mock provider (never in a protected
    environment). Otherwise the platform key for ``WAVIA_POST_CALL_LLM_PROVIDER``
    (default ``groq``) is required; without it intelligence stays disabled and
    the jobs runner reports why.
    """
    if (
        provider_runtime_status()["provider_mode"] == "mock"
        and not is_protected_environment()
    ):
        mock = MockIntelligenceProvider()
        return mock, mock

    from core.providers.factory import build_llm_provider
    from core.providers.spec import DEFAULT_PROVIDER_CATALOG
    from core.secrets.platform import EnvironmentPlatformSecretProvider

    provider_id = (
        (os.environ.get("WAVIA_POST_CALL_LLM_PROVIDER") or "groq").strip().lower()
    )
    if provider_id not in {"groq", "gemini", "openai"}:
        return None
    credential = EnvironmentPlatformSecretProvider().resolve(provider_id, "api_key")
    if credential is None:
        return None
    spec = DEFAULT_PROVIDER_CATALOG.require(provider_id)
    model_id = (
        os.environ.get("WAVIA_POST_CALL_LLM_MODEL") or ""
    ).strip() or spec.default_models[0]
    llm = build_llm_provider(provider_id, api_key=credential.secret, model=model_id)
    provider = LLMIntelligenceProvider(llm, provider_id=provider_id, model_id=model_id)
    return provider, provider


def post_call_disabled_reason() -> str:
    provider_id = (
        (os.environ.get("WAVIA_POST_CALL_LLM_PROVIDER") or "groq").strip().lower()
    )
    return (
        f"no post-call intelligence provider: set PLATFORM_{provider_id.upper()}_API_KEY "
        "(provider chosen by WAVIA_POST_CALL_LLM_PROVIDER: groq, gemini or openai)"
    )
