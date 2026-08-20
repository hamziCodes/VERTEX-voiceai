"""UCVE Multilingual Language Registry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.language.rtl_validation import RTLVoiceValidator


@dataclass
class LanguageProfile:
    """Configuration profile for supported language."""

    code: str
    name: str = ""
    directive_prompt_path: str = ""
    vad_silence_override_ms: int = 500
    tts_voice_id: str = ""
    tts_first_chunk_word_count: int = 3
    script_direction: str = "ltr"
    code_switching_default: bool = False
    redaction_script_coverage: str = "full"
    cs_measure_only: bool = False


class LanguageRegistry:
    """Registry loading language profiles and performing RTL publish validation."""

    def __init__(self) -> None:
        self._profiles: dict[str, LanguageProfile] = {}

    @classmethod
    def load_defaults(cls) -> LanguageRegistry:
        """Load default YAML language profiles (en, ur, ar, ms)."""
        reg = cls()
        profiles_dir = Path(__file__).resolve().parent / "profiles"

        for yaml_file in profiles_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                profile = LanguageProfile(
                    code=data["code"],
                    name=data.get("name", ""),
                    directive_prompt_path=data.get("directive_prompt_path", ""),
                    vad_silence_override_ms=data.get("vad_silence_override_ms", 500),
                    tts_voice_id=data.get("tts_voice_id", ""),
                    tts_first_chunk_word_count=data.get("tts_first_chunk_word_count", 3),
                    script_direction=data.get("script_direction", "ltr"),
                    code_switching_default=data.get("code_switching_default", False),
                    redaction_script_coverage=data.get("redaction_script_coverage", "full"),
                    cs_measure_only=data.get("cs_measure_only", False),
                )
                reg._profiles[profile.code] = profile
            except Exception:
                pass

        return reg

    def get_profile(self, code: str) -> LanguageProfile | None:
        """Retrieve profile by language code."""
        return self._profiles.get(code.lower())

    def validate_voice_for_publish(self, language_code: str, tts_voice_id: str) -> bool:
        """Validate voice ID for language before agent publish."""
        return RTLVoiceValidator.validate_voice_for_publish(language_code, tts_voice_id)
