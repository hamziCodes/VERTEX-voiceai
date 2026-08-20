"""UCVE Deterministic Text Normalizer."""

from __future__ import annotations

import re
from typing import Any

from core.language.lexicon import PronunciationLexicon
from core.language.normalization_result import NormalizationResult
from core.language.numerals import NumeralNormalizer


class TextNormalizer:
    """Text normalizer converting LLM output to clean, spoken-form TTS input."""

    def normalize(
        self,
        text: str,
        language: str = "en",
        lexicon: dict[str, str] | None = None,
        attempt: int = 0,
    ) -> NormalizationResult:
        """Strip markdown, normalize numerals, apply lexicon, and check script consistency."""
        warnings: list[str] = []
        needs_regen = False

        # Step 1: Strip markdown artifacts
        text = re.sub(r"\*\*|\*|`", "", text)
        text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)

        # Step 2: Script consistency check
        # Rule: Latin English tokens in Urdu context are pass-through (Minglish)
        lang_code = language.lower()
        if lang_code == "ur":
            # Check for non-Latin and non-Arabic/Urdu script tokens (e.g., Cyrillic/Chinese)
            if re.search(r"[\u0400-\u04FF\u4E00-\u9FFF]", text):
                needs_regen = True
                warnings.append("Incompatible non-Urdu/non-English script detected.")
        elif lang_code == "en":
            # Non-Latin script in English context triggers regeneration warning
            if re.search(r"[\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF]", text):
                needs_regen = True
                warnings.append("Non-English script tokens detected in English text.")

        # Step 3: Numeral spoken-form conversion
        text = NumeralNormalizer.convert_numerals(text, language=lang_code)

        # Step 4: Tenant lexicon substitution
        if lexicon:
            text = PronunciationLexicon.apply_lexicon(text, lexicon)

        return NormalizationResult(
            text=text.strip(),
            warnings=warnings,
            needs_regeneration=needs_regen,
            regeneration_attempt=attempt,
        )
