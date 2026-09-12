"""UCVE Agent Builder - Structured Extraction Field Cap Rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from control_plane.agents.validation.rules.base import BaseValidationRule, ValidationErrorItem

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig

MAX_EXTRACTION_FIELDS = 50


class ExtractionFieldCapRule(BaseValidationRule):
    """Enforces that structured extraction schemas do not exceed the 50-field limit."""

    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        errors: list[ValidationErrorItem] = []
        schema = config.extraction_schema
        if not schema:
            return errors

        # Schema can define fields under "fields" or JSON Schema "properties"
        fields = schema.get("fields") or schema.get("properties") or {}
        field_count = len(fields) if isinstance(fields, (list, dict)) else 0

        if field_count > MAX_EXTRACTION_FIELDS:
            errors.append(
                ValidationErrorItem(
                    code="EXTRACTION_FIELD_CAP_EXCEEDED",
                    message=(
                        f"Extraction schema contains {field_count} fields, which exceeds the maximum limit "
                        f"of {MAX_EXTRACTION_FIELDS} fields."
                    ),
                    field="extraction_schema",
                )
            )

        return errors
