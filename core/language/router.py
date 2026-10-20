"""UCVE Real-Time Language Router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LanguageRouterConfig:
    """Config rules governing language switch threshold and debounce."""

    immediate_switch_word_count: int = 3
    consecutive_switch_count: int = 2


class LanguageRouter:
    """Real-time language router switching conversation language based on STT hypotheses (MULTI port)."""

    def __init__(self, config: LanguageRouterConfig | None = None) -> None:
        self.config = config or LanguageRouterConfig()
        self._pending_language: str | None = None
        self._pending_count: int = 0
        self._supported_languages: set[str] = {"en", "ur", "ar", "ms"}

    def set_supported_languages(self, languages: tuple[str, ...]) -> None:
        """Constrain runtime language switching to the published agent plan."""

        normalized = {language.strip().lower() for language in languages if language.strip()}
        if not normalized:
            raise ValueError("At least one supported language is required.")
        self._supported_languages = normalized
        self._pending_language = None
        self._pending_count = 0

    def route(self, transcript: Any, current_language: str) -> str:
        """Route transcript hypothesis and return target language code."""
        # Extract text and detected language attribute
        text = ""
        detected_lang = None

        if isinstance(transcript, dict):
            text = transcript.get("text", "")
            detected_lang = transcript.get("language")
        else:
            text = getattr(transcript, "text", "")
            detected_lang = getattr(transcript, "language", None)

        if not detected_lang or detected_lang.lower() not in self._supported_languages:
            return current_language  # Unsupported or missing language keeps current

        detected_lang = detected_lang.lower()
        if detected_lang == current_language:
            self._pending_language = None
            self._pending_count = 0
            return current_language

        words = [w for w in text.strip().split() if w]
        word_count = len(words)

        # Immediate switch for >= 3 words (MULTI logic)
        if word_count >= self.config.immediate_switch_word_count:
            self._pending_language = None
            self._pending_count = 0
            return detected_lang

        # Debounce switch for < 3 words (requires 2 consecutive detections)
        if self._pending_language == detected_lang:
            self._pending_count += 1
        else:
            self._pending_language = detected_lang
            self._pending_count = 1

        if self._pending_count >= self.config.consecutive_switch_count:
            self._pending_language = None
            self._pending_count = 0
            return detected_lang

        return current_language
