from __future__ import annotations

import io

from .base import IngestionParseError, ParsedDocument, ParsedSection


def parse_docx(content: bytes) -> ParsedDocument:
    try:
        from docx import Document

        document = Document(io.BytesIO(content))
    except Exception as exc:
        raise IngestionParseError(
            "docx_malformed", "DOCX file could not be parsed."
        ) from exc
    sections: list[ParsedSection] = []
    total = 0
    for index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        total += len(text)
        if text:
            sections.append(ParsedSection(text, {"paragraph": index}))
    for table_number, table in enumerate(document.tables, start=1):
        for row_number, row in enumerate(table.rows, start=1):
            text = " | ".join(cell.text.strip() for cell in row.cells)
            total += len(text)
            if text.strip(" |"):
                sections.append(
                    ParsedSection(text, {"table": table_number, "row": row_number})
                )
    if total > 500_000:
        raise IngestionParseError(
            "character_limit_exceeded", "DOCX contains too much text."
        )
    return ParsedDocument(sections)
