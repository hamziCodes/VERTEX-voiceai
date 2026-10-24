from __future__ import annotations

import csv
import io

from .base import IngestionParseError, ParsedDocument, ParsedSection, decode_text


def parse_csv(content: bytes) -> ParsedDocument:
    text = decode_text(content)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows: list[ParsedSection] = []
    reader = csv.reader(io.StringIO(text), dialect)
    for row_number, row in enumerate(reader, start=1):
        if row_number > 50_000:
            raise IngestionParseError(
                "row_limit_exceeded", "CSV exceeds the row limit."
            )
        if len(row) > 256:
            raise IngestionParseError(
                "column_limit_exceeded", "CSV exceeds the column limit."
            )
        if any(len(cell) > 32_768 for cell in row):
            raise IngestionParseError(
                "cell_limit_exceeded", "CSV contains an oversized cell."
            )
        rows.append(ParsedSection(" | ".join(row), {"row": row_number}))
    return ParsedDocument(rows)
