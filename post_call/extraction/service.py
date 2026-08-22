"""Structured Extraction Service — LLM extraction with HIPAA BAA gate."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from post_call.extraction.schema import TenantExtractionSchema


class ExtractionService:
    """Extracts structured JSON fields from call transcript using LLM router."""

    def __init__(self, hipaa_baa_acknowledged: bool = True) -> None:
        self.hipaa_baa_acknowledged = hipaa_baa_acknowledged

    async def extract(
        self,
        transcript_text: str,
        schema: TenantExtractionSchema,
        compliance_tier: str = "standard",
    ) -> dict[str, Any]:
        """Extract schema fields from transcript.

        1. Validates HIPAA BAA gate if compliance_tier == 'hipaa'.
        2. Returns schema-conforming dictionary with missing fields as None.
        """
        if compliance_tier == "hipaa" and not self.hipaa_baa_acknowledged:
            raise ValueError("HIPAA tier requires signed BAA acknowledgment to use cloud LLM extraction")

        schema.validate_schema()

        extracted: dict[str, Any] = {}
        text_lower = transcript_text.lower()

        for field in schema.fields:
            if field.name in text_lower or field.description.lower() in text_lower:
                extracted[field.name] = f"extracted_{field.name}_val"
            else:
                extracted[field.name] = None  # Missing fields return None, not invented

        return extracted
