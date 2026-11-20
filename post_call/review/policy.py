"""Deterministic policy for routing post-call intelligence to review."""

from __future__ import annotations

from post_call.extraction.schema import TenantExtractionSchema
from post_call.extraction.service import ExtractionResult
from post_call.models.policy import PostCallPolicy


class ReviewPolicy:
    def reasons(
        self,
        *,
        policy: PostCallPolicy,
        schema: TenantExtractionSchema | None,
        extraction: ExtractionResult | None,
        verification_issue_codes: tuple[str, ...],
        external_action_configured: bool,
    ) -> tuple[str, ...]:
        reasons: set[str] = set()
        if external_action_configured:
            reasons.add("external_action_policy")
        if schema is not None and extraction is not None:
            for field in schema.fields:
                value = extraction.fields[field.name]
                if field.sensitive and value.value is not None:
                    reasons.add(f"sensitive_field:{field.name}")
                if (
                    value.value is not None
                    and value.confidence < field.confidence_threshold
                ):
                    reasons.add(f"low_confidence:{field.name}")
        reasons.update(f"verification:{code}" for code in verification_issue_codes)
        return tuple(sorted(reasons))
