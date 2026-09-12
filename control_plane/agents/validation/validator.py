"""UCVE Agent Builder - Agent Configuration Validation Engine."""

from __future__ import annotations

from typing import Any

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.validation.rules import (
    ArabicRTLVoiceRule,
    BaseValidationRule,
    ExtractionFieldCapRule,
    HIPAAGateRule,
    MinProvidersRule,
    TelephonyTrunkRule,
    ValidationErrorItem,
)


class ValidationResult:
    """Encapsulates the outcome of an agent configuration validation run."""

    def __init__(self, is_valid: bool, errors: list[ValidationErrorItem]) -> None:
        self.is_valid = is_valid
        self.errors = errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": [e.to_dict() for e in self.errors],
        }

    def raise_if_invalid(self) -> None:
        if not self.is_valid:
            msgs = "; ".join(f"[{e.code}] {e.message}" for e in self.errors)
            raise ValueError(f"AgentConfig validation failed: {msgs}")


class AgentConfigValidator:
    """Master validation engine enforcing resilience, language, compliance, and schema invariants."""

    def __init__(self, custom_rules: list[BaseValidationRule] | None = None) -> None:
        self.rules: list[BaseValidationRule] = custom_rules or [
            MinProvidersRule(),
            ArabicRTLVoiceRule(),
            ExtractionFieldCapRule(),
            HIPAAGateRule(),
            TelephonyTrunkRule(),
        ]

    def validate(self, config: AgentConfig) -> ValidationResult:
        all_errors: list[ValidationErrorItem] = []
        for rule in self.rules:
            errs = rule.validate(config)
            all_errors.extend(errs)

        return ValidationResult(is_valid=len(all_errors) == 0, errors=all_errors)
