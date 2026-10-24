from __future__ import annotations

import io

from .base import IngestionParseError, ParsedDocument, ParsedSection


def parse_xlsx(content: bytes) -> ParsedDocument:
    try:
        from openpyxl import load_workbook  # type: ignore[import-untyped]

        workbook = load_workbook(
            io.BytesIO(content), read_only=True, data_only=True, keep_links=False
        )
    except Exception as exc:
        raise IngestionParseError(
            "xlsx_malformed", "XLSX file could not be parsed."
        ) from exc
    if len(workbook.sheetnames) > 50:
        workbook.close()
        raise IngestionParseError(
            "sheet_limit_exceeded", "XLSX exceeds the sheet limit."
        )
    sections: list[ParsedSection] = []
    total_rows = 0
    try:
        for sheet in workbook.worksheets:
            for row_number, row in enumerate(
                sheet.iter_rows(values_only=True), start=1
            ):
                total_rows += 1
                if total_rows > 50_000:
                    raise IngestionParseError(
                        "row_limit_exceeded", "XLSX exceeds the row limit."
                    )
                values = ["" if value is None else str(value) for value in row]
                if len(values) > 256:
                    raise IngestionParseError(
                        "column_limit_exceeded", "XLSX exceeds the column limit."
                    )
                if any(len(value) > 32_768 for value in values):
                    raise IngestionParseError(
                        "cell_limit_exceeded", "XLSX contains an oversized cell."
                    )
                if any(values):
                    sections.append(
                        ParsedSection(
                            " | ".join(values),
                            {"sheet": sheet.title, "row": row_number},
                        )
                    )
    finally:
        workbook.close()
    return ParsedDocument(sections)
