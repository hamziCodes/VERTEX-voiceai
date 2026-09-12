"""UCVE Agent Builder - Provider Priority Chain Resilience Rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from control_plane.agents.validation.rules.base import BaseValidationRule, ValidationErrorItem

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig


class MinProvidersRule(BaseValidationRule):
    """Enforces that STT, LLM, and TTS each have at least 2 enabled provider routes for resilience."""

    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        errors: list[ValidationErrorItem] = []
        critical_categories = [
            ("stt", config.providers.stt),
            ("llm", config.providers.llm),
            ("tts", config.providers.tts),
        ]

        for cat_name, chains in critical_categories:
            if not chains:
                errors.append(
                    ValidationErrorItem(
                        code="MISSING_PROVIDER_CATEGORY",
                        message=f"Agent must configure provider chains for category '{cat_name}'.",
                        field=f"providers.{cat_name}",
                    )
                )
                continue

            for chain in chains:
                enabled_count = chain.enabled_route_count()
                if enabled_count < 2:
                    errors.append(
                        ValidationErrorItem(
                            code="INSUFFICIENT_PROVIDER_ROUTES",
                            message=(
                                f"Priority chain for category '{cat_name}' and language '{chain.language}' "
                                f"must have at least 2 enabled routes for resilience (found {enabled_count})."
                            ),
                            field=f"providers.{cat_name}",
                        )
                    )

        return errors
