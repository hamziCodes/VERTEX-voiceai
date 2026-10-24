from __future__ import annotations

from core.rag.ingestion.validation import ValidatedUpload

from .base import ParsedDocument
from .csv import parse_csv
from .docx import parse_docx
from .faq import parse_faq
from .pdf import parse_pdf
from .text import parse_text
from .xlsx import parse_xlsx


def parse_document(upload: ValidatedUpload, content: bytes) -> ParsedDocument:
    if upload.source_type == "pdf":
        return parse_pdf(content)
    if upload.source_type == "docx":
        return parse_docx(content)
    if upload.source_type == "txt":
        return parse_text(content)
    if upload.source_type == "markdown":
        return parse_text(content, markdown=True)
    if upload.source_type == "csv":
        return parse_csv(content)
    if upload.source_type == "xlsx":
        return parse_xlsx(content)
    if upload.source_type == "faq":
        return parse_faq(content)
    raise AssertionError(f"No parser registered for {upload.source_type}")
