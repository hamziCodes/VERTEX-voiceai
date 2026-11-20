from __future__ import annotations

from .base import IngestionParseError, ParsedDocument, ParsedSection, decode_text


def parse_text(content: bytes, *, markdown: bool = False) -> ParsedDocument:
    text = decode_text(content)
    if len(text) > 500_000:
        raise IngestionParseError(
            "character_limit_exceeded", "Document contains too much text."
        )
    sections: list[ParsedSection] = []
    heading = "Document"
    buffer: list[str] = []

    def flush(line_number: int) -> None:
        body = "\n".join(buffer).strip()
        if body:
            rendered = (
                f"{heading}\n{body}" if markdown and heading != "Document" else body
            )
            sections.append(
                ParsedSection(rendered, {"heading": heading, "line": line_number})
            )
        buffer.clear()

    for line_number, line in enumerate(text.splitlines(), start=1):
        if markdown and line.lstrip().startswith("#"):
            flush(line_number)
            heading = line.lstrip("# ").strip() or "Untitled"
        else:
            buffer.append(line)
    flush(max(1, len(text.splitlines())))
    return ParsedDocument(sections)
