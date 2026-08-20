"""UCVE Text Normalization Result Entity."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NormalizationResult:
    """Result of text normalization and script consistency inspection."""

    text: str
    warnings: list[str] = field(default_factory=list)
    needs_regeneration: bool = False
    regeneration_attempt: int = 0
