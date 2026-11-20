from __future__ import annotations

import json
from uuid import uuid4

import pytest

from post_call.extraction.schema import ExtractionField, TenantExtractionSchema
from post_call.extraction.service import ExtractionService, IntelligenceOutputError
from post_call.models.diarized_turn import DiarizedTurn
from post_call.summarization.service import SummarizationService


class _ExtractionProvider:
    provider_id = "fixture"
    model_id = "fixture-extract-v1"

    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def extract_json(self, **_: object) -> object:
        return self.payload


class _SummaryProvider:
    provider_id = "fixture"
    model_id = "fixture-summary-v1"

    def __init__(self, payload: object) -> None:
        self.payload = payload

    async def summarize_json(self, **_: object) -> object:
        return self.payload


def _turns() -> list[DiarizedTurn]:
    return [
        DiarizedTurn(
            speaker="user",
            text="My name is Ayesha and I need a Tuesday appointment.",
            start_ms=0,
            end_ms=900,
        ),
        DiarizedTurn(
            speaker="assistant",
            text="I can help with that request.",
            start_ms=901,
            end_ms=1400,
        ),
    ]


@pytest.mark.asyncio
async def test_extraction_accepts_only_schema_fields_with_grounded_evidence() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[
            ExtractionField(name="patient_name", required=True),
            ExtractionField(name="insurance_id"),
        ],
    )
    provider = _ExtractionProvider(
        json.dumps(
            {
                "fields": {
                    "patient_name": {
                        "value": "Ayesha",
                        "confidence": 0.97,
                        "evidence": [{"turn_id": 0, "quote": "My name is Ayesha"}],
                    },
                    "insurance_id": {
                        "value": None,
                        "confidence": 0.0,
                        "evidence": [],
                    },
                }
            }
        )
    )

    result = await ExtractionService(provider=provider).extract(_turns(), schema)

    assert result.fields["patient_name"].value == "Ayesha"
    assert result.fields["patient_name"].source_turn_ids == (0,)
    assert result.fields["insurance_id"].value is None
    assert result.provider_id == "fixture"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        {"fields": {"invented": {"value": "x", "confidence": 1, "evidence": []}}},
        {
            "fields": {
                "patient_name": {
                    "value": "Ayesha",
                    "confidence": 0.9,
                    "evidence": [{"turn_id": 1, "quote": "Ayesha"}],
                }
            }
        },
    ],
)
async def test_invalid_or_ungrounded_extraction_fails_without_fabrication(
    payload: object,
) -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(), fields=[ExtractionField(name="patient_name")]
    )

    with pytest.raises(IntelligenceOutputError):
        await ExtractionService(provider=_ExtractionProvider(payload)).extract(
            _turns(), schema
        )


@pytest.mark.asyncio
async def test_extraction_rejects_value_that_violates_declared_field_type() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[ExtractionField(name="party_size", type="number")],
    )
    payload = {
        "fields": {
            "party_size": {
                "value": "four",
                "confidence": 0.99,
                "evidence": [{"turn_id": 0, "quote": "name is Ayesha"}],
            }
        }
    }

    with pytest.raises(IntelligenceOutputError, match="declared field type"):
        await ExtractionService(provider=_ExtractionProvider(payload)).extract(
            _turns(), schema
        )


@pytest.mark.asyncio
async def test_summary_requires_evidence_and_preserves_provider_identity() -> None:
    payload = {
        "executive_summary": "Ayesha requested a Tuesday appointment.",
        "key_takeaways": ["Appointment requested"],
        "sentiment_trajectory": ["neutral"],
        "evidence": [{"turn_id": 0, "quote": "I need a Tuesday appointment"}],
    }

    result = await SummarizationService(provider=_SummaryProvider(payload)).summarize(
        _turns()
    )

    assert result is not None
    assert result.provider_id == "fixture"
    assert result.source_turn_ids == (0,)


@pytest.mark.asyncio
async def test_empty_transcript_returns_no_summary_without_calling_provider() -> None:
    result = await SummarizationService(
        provider=_SummaryProvider("not-json")
    ).summarize([])

    assert result is None
