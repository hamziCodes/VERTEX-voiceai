"""UCVE Agent Builder - Telephony Trunk Validation Rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from control_plane.agents.validation.rules.base import BaseValidationRule, ValidationErrorItem

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig


class TelephonyTrunkRule(BaseValidationRule):
    """Enforces that telephony-enabled agents configure at least one active trunk."""

    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        errors: list[ValidationErrorItem] = []
        if not config.telephony:
            return errors

        enabled = bool(config.telephony.get("enabled", False))
        if not enabled:
            return errors

        trunks = config.telephony.get("trunks", [])
        if not trunks:
            errors.append(
                ValidationErrorItem(
                    code="TELEPHONY_TRUNK_REQUIRED",
                    message="Telephony is enabled but no active SIP/PSTN trunks are configured.",
                    field="telephony.trunks",
                )
            )

        return errors
