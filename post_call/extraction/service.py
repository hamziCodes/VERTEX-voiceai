"""Strict, evidence-backed structured extraction."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from post_call.extraction.provider import ExtractionProvider
from post_call.extraction.schema import TenantExtractionSchema
from post_call.models.diarized_turn import DiarizedTurn


class IntelligenceOutputError(ValueError):
    """Raised when provider output cannot be safely persisted."""


class IntelligenceProviderUnavailableError(RuntimeError):
    pass


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_id: int = Field(ge=0)
    quote: str = Field(min_length=1, max_length=500)


class _RawExtractedField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[EvidenceRef, ...] = ()


class _RawExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: dict[str, _RawExtractedField]


class ExtractedField(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Any | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_turn_ids: tuple[int, ...] = ()


class ExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    fields: dict[str, ExtractedField]
    provider_id: str
    model_id: str


def parse_provider_json(raw: object) -> object:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise IntelligenceOutputError("Provider returned invalid JSON.") from exc
    return raw


def evidence_turn_ids(
    evidence: tuple[EvidenceRef, ...], turns: list[DiarizedTurn]
) -> tuple[int, ...]:
    ids: list[int] = []
    for item in evidence:
        if item.turn_id >= len(turns):
            raise IntelligenceOutputError("Evidence references an unknown turn.")
        if item.quote.casefold() not in turns[item.turn_id].text.casefold():
            raise IntelligenceOutputError("Evidence quote is not present in its turn.")
        if item.turn_id not in ids:
            ids.append(item.turn_id)
    return tuple(ids)


def value_matches_field_type(value: Any, field_type: str) -> bool:
    if field_type in {"string", "datetime", "phone"}:
        return isinstance(value, str)
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "boolean":
        return isinstance(value, bool)
    return False


class ExtractionService:
    """Validate provider JSON against the tenant schema and transcript evidence."""

    def __init__(
        self,
        provider: ExtractionProvider | None = None,
        *,
        hipaa_baa_acknowledged: bool = True,
    ) -> None:
        self.provider = provider
        self.hipaa_baa_acknowledged = hipaa_baa_acknowledged

    async def extract(
        self,
        turns: list[DiarizedTurn],
        schema: TenantExtractionSchema,
        compliance_tier: str = "standard",
    ) -> ExtractionResult:
        if compliance_tier == "hipaa" and not self.hipaa_baa_acknowledged:
            raise PermissionError(
                "HIPAA tier requires signed BAA acknowledgment for extraction."
            )
        if self.provider is None:
            raise IntelligenceProviderUnavailableError(
                "A structured extraction provider is required."
            )
        schema.validate_schema()
        try:
            raw = await self.provider.extract_json(turns=turns, schema=schema)
            parsed = _RawExtraction.model_validate(parse_provider_json(raw))
        except IntelligenceOutputError:
            raise
        except (ValidationError, TypeError, ValueError) as exc:
            raise IntelligenceOutputError(
                "Provider extraction failed schema validation."
            ) from exc

        expected = {field.name: field for field in schema.fields}
        unknown = set(parsed.fields) - set(expected)
        if unknown:
            raise IntelligenceOutputError("Provider returned an unknown field.")

        fields: dict[str, ExtractedField] = {}
        for name in expected:
            candidate = parsed.fields.get(name)
            if candidate is None:
                fields[name] = ExtractedField(value=None, confidence=0.0)
                continue
            if candidate.value is None:
                if candidate.evidence or candidate.confidence != 0.0:
                    raise IntelligenceOutputError(
                        "Missing extraction values cannot claim confidence or evidence."
                    )
                fields[name] = ExtractedField(value=None, confidence=0.0)
                continue
            if not candidate.evidence:
                raise IntelligenceOutputError(
                    "Non-null extraction values require transcript evidence."
                )
            if not value_matches_field_type(candidate.value, expected[name].type):
                raise IntelligenceOutputError(
                    "Provider value does not match the declared field type."
                )
            fields[name] = ExtractedField(
                value=candidate.value,
                confidence=candidate.confidence,
                source_turn_ids=evidence_turn_ids(candidate.evidence, turns),
            )
        return ExtractionResult(
            fields=fields,
            provider_id=self.provider.provider_id,
            model_id=self.provider.model_id,
        )
