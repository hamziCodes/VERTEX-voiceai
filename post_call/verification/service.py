"""Verification Service — Validates phone, dates, and extraction confidence."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from post_call.extraction.schema import TenantExtractionSchema
from post_call.verification.datetime import parse_and_verify_datetime
from post_call.verification.phone import normalize_phone_e164


class VerificationIssue(BaseModel):
    """Verification issue model for invalid or low-confidence extracted fields."""

    field_name: str
    error_type: str  # invalid_phone / invalid_datetime / low_confidence / missing_required
    description: str
    confidence: float = 1.0


class VerificationService:
    """Verifies extracted fields against schema rules and data types."""

    def verify(
        self,
        extracted: dict[str, Any],
        schema: TenantExtractionSchema,
        confidence_map: dict[str, float] | None = None,
        min_confidence_threshold: float = 0.75,
    ) -> list[VerificationIssue]:
        """Verify extracted field map and return list of VerificationIssue items."""
        issues: list[VerificationIssue] = []
        conf_map = confidence_map or {}

        field_rules = {f.name: f for f in schema.fields}

        for k, v in extracted.items():
            field_rule = field_rules.get(k)
            confidence = conf_map.get(k, 1.0)

            # Check low confidence
            if confidence < min_confidence_threshold:
                issues.append(
                    VerificationIssue(
                        field_name=k,
                        error_type="low_confidence",
                        description=f"Field '{k}' confidence ({confidence}) below threshold ({min_confidence_threshold})",
                        confidence=confidence,
                    )
                )

            # Check required missing
            if field_rule and field_rule.required and v is None:
                issues.append(
                    VerificationIssue(
                        field_name=k,
                        error_type="missing_required",
                        description=f"Required field '{k}' is missing",
                        confidence=confidence,
                    )
                )

            # Check phone format if field type == phone or name contains phone
            if v and field_rule and field_rule.type == "phone":
                normalized = normalize_phone_e164(str(v))
                if not normalized:
                    issues.append(
                        VerificationIssue(
                            field_name=k,
                            error_type="invalid_phone",
                            description=f"Field '{k}' value '{v}' is not a valid E.164 phone number",
                            confidence=confidence,
                        )
                    )

            # Check datetime format if field type == datetime
            if v and field_rule and field_rule.type == "datetime":
                parsed_dt = parse_and_verify_datetime(str(v))
                if not parsed_dt:
                    issues.append(
                        VerificationIssue(
                            field_name=k,
                            error_type="invalid_datetime",
                            description=f"Field '{k}' value '{v}' is not a valid ISO datetime",
                            confidence=confidence,
                        )
                    )

        return issues
