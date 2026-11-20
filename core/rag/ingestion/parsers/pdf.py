from __future__ import annotations

import io

from .base import IngestionParseError, ParsedDocument, ParsedSection


def parse_pdf(content: bytes) -> ParsedDocument:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise IngestionParseError(
                "pdf_encrypted", "Encrypted PDFs are not supported."
            )
        if len(reader.pages) > 500:
            raise IngestionParseError(
                "page_limit_exceeded", "PDF exceeds the page limit."
            )
        sections: list[ParsedSection] = []
        total_characters = 0
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            total_characters += len(text)
            if total_characters > 500_000:
                raise IngestionParseError(
                    "character_limit_exceeded", "PDF contains too much text."
                )
            if text:
                sections.append(ParsedSection(text, {"page": page_number}))
    except IngestionParseError:
        raise
    except Exception as exc:
        raise IngestionParseError(
            "pdf_malformed", "PDF file could not be parsed."
        ) from exc
    if not sections:
        raise IngestionParseError(
            "pdf_no_extractable_text",
            "PDF contains no extractable text; OCR is not enabled.",
        )
    return ParsedDocument(sections)
