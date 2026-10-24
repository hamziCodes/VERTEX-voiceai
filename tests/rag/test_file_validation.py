from __future__ import annotations

import io
import zipfile

import pytest

from core.rag.ingestion.validation import IngestionValidationError, validate_upload


def test_rejects_path_traversal_and_mime_mismatch() -> None:
    with pytest.raises(IngestionValidationError, match="file_name_invalid"):
        validate_upload("../policy.txt", "text/plain", b"safe")
    with pytest.raises(IngestionValidationError, match="media_type_mismatch"):
        validate_upload("policy.pdf", "application/pdf", b"not a pdf")


def test_rejects_binary_text_and_unsupported_formats() -> None:
    with pytest.raises(IngestionValidationError, match="binary_text"):
        validate_upload("notes.txt", "text/plain", b"hello\x00world")
    with pytest.raises(IngestionValidationError, match="unsupported_format"):
        validate_upload("legacy.doc", "application/msword", b"legacy")


def test_rejects_office_archive_bomb_metadata_and_macros() -> None:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("[Content_Types].xml", "x" * 100_001)
        bundle.writestr("word/document.xml", "<document/>")
        bundle.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(IngestionValidationError) as error:
        validate_upload(
            "unsafe.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            archive.getvalue(),
        )
    assert error.value.code in {"office_macro_forbidden", "archive_ratio_exceeded"}


def test_valid_text_returns_normalized_metadata_and_digest() -> None:
    validated = validate_upload("  guide.TXT  ", "text/plain", b"Hello world")
    assert validated.display_name == "guide.TXT"
    assert validated.source_type == "txt"
    assert validated.byte_count == 11
    assert len(validated.checksum_sha256) == 64
