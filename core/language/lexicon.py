"""UCVE Tenant Pronunciation Lexicon Lookup."""

from __future__ import annotations

import re


class PronunciationLexicon:
    """Applies tenant-specific custom pronunciation rules (grapheme to plain-text replacement)."""

    @classmethod
    def apply_lexicon(
        cls, text: str, lexicon: dict[str, str] | None = None
    ) -> str:
        """Replace brand/SKU terms with tenant-defined pronunciation spellings."""
        if not lexicon:
            return text

        for term, pronunciation in lexicon.items():
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            text = pattern.sub(pronunciation, text)

        return text
