"""UCVE Agent Builder - Compliance & HIPAA BAA Validation Rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from control_plane.agents.validation.rules.base import BaseValidationRule, ValidationErrorItem

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig


class HIPAAGateRule(BaseValidationRule):
    """Enforces that HIPAA tier agents require explicit HIPAA BAA acknowledgement."""

    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        errors: list[ValidationErrorItem] = []
        tier = str(config.compliance.get("tier", "standard")).strip().lower()
        baa_ack = bool(config.compliance.get("hipaa_baa_acknowledged", False))

        if tier == "hipaa" and not baa_ack:
            errors.append(
                ValidationErrorItem(
                    code="HIPAA_BAA_REQUIRED",
                    message="Agents configured for HIPAA compliance require tenant HIPAA BAA acknowledgement.",
                    field="compliance.hipaa_baa_acknowledged",
                )
            )

        return errors
