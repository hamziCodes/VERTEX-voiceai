from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class IngestionParseError(ValueError):
    """A typed, safe-to-display document parsing failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class ParsedSection:
    text: str
    citation: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    sections: list[ParsedSection]
    warnings: list[str] = field(default_factory=list)


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionParseError(
        "text_encoding_unsupported", "Text encoding is unsupported."
    )
