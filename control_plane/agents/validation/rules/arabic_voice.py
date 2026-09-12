"""UCVE Agent Builder - Arabic RTL Voice Validation Rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

from control_plane.agents.validation.rules.base import BaseValidationRule, ValidationErrorItem

if TYPE_CHECKING:
    from control_plane.agents.models.agent_config import AgentConfig

KNOWN_ARABIC_RTL_VOICES = {
    "ar-sa-naima",
    "ar-ae-fatima",
    "ar-eg-salma",
    "ar-default",
    "orpheus-arabic-saudi",
    "cartesia-arabic-v1",
    "arabic-native",
}


class ArabicRTLVoiceRule(BaseValidationRule):
    """Enforces that if Arabic ('ar') is enabled, an RTL-capable Arabic voice must be selected."""

    def validate(self, config: AgentConfig) -> list[ValidationErrorItem]:
        errors: list[ValidationErrorItem] = []
        is_arabic = any(lang.strip().lower().startswith("ar") for lang in config.languages)
        if not is_arabic:
            return errors

        voice = (config.persona.voice_id or "").strip().lower()
        is_rtl_voice = (
            voice in KNOWN_ARABIC_RTL_VOICES
            or "arabic" in voice
            or voice.startswith("ar-")
            or voice.endswith("-ar")
        )

        if not is_rtl_voice:
            errors.append(
                ValidationErrorItem(
                    code="ARABIC_RTL_VOICE_REQUIRED",
                    message=(
                        f"Arabic language ('ar') requires an RTL-capable Arabic voice ID. "
                        f"Voice '{config.persona.voice_id}' does not satisfy Arabic RTL phonetic requirements."
                    ),
                    field="persona.voice_id",
                )
            )

        return errors
