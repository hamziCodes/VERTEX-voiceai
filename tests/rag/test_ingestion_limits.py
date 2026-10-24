from __future__ import annotations

import json

import pytest

from core.rag.ingestion.parsers.base import IngestionParseError
from core.rag.ingestion.parsers.registry import parse_document
from core.rag.ingestion.validation import IngestionValidationError, validate_upload


def test_rejects_oversized_text_before_parsing() -> None:
    with pytest.raises(IngestionValidationError, match="file_too_large"):
        validate_upload("huge.txt", "text/plain", b"x" * (5 * 1024 * 1024 + 1))


def test_rejects_excessive_csv_rows_and_large_cells() -> None:
    too_many_rows = b"a\n" * 50_001
    with pytest.raises(IngestionParseError, match="row_limit_exceeded"):
        parse_document(
            validate_upload("rows.csv", "text/csv", too_many_rows), too_many_rows
        )
    huge_cell = ("x" * 32_769).encode()
    with pytest.raises(IngestionParseError, match="cell_limit_exceeded"):
        parse_document(validate_upload("cell.csv", "text/csv", huge_cell), huge_cell)


def test_rejects_too_many_faq_items() -> None:
    content = json.dumps([{"question": "q", "answer": "a"}] * 1001).encode()
    with pytest.raises(IngestionParseError, match="faq_limit_exceeded"):
        parse_document(
            validate_upload("faq.json", "application/json", content), content
        )
