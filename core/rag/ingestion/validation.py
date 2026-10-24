from __future__ import annotations

import hashlib
import io
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePath


class IngestionValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.safe_message = message


@dataclass(frozen=True, slots=True)
class FormatPolicy:
    source_type: str
    media_types: frozenset[str]
    max_bytes: int


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    display_name: str
    source_type: str
    media_type: str
    byte_count: int
    checksum_sha256: str


_MIB = 1024 * 1024
FORMAT_POLICIES: dict[str, FormatPolicy] = {
    ".pdf": FormatPolicy("pdf", frozenset({"application/pdf"}), 20 * _MIB),
    ".docx": FormatPolicy(
        "docx",
        frozenset(
            {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
        ),
        10 * _MIB,
    ),
    ".txt": FormatPolicy("txt", frozenset({"text/plain"}), 5 * _MIB),
    ".md": FormatPolicy(
        "markdown", frozenset({"text/markdown", "text/plain"}), 5 * _MIB
    ),
    ".markdown": FormatPolicy(
        "markdown", frozenset({"text/markdown", "text/plain"}), 5 * _MIB
    ),
    ".csv": FormatPolicy(
        "csv", frozenset({"text/csv", "application/csv", "text/plain"}), 10 * _MIB
    ),
    ".xlsx": FormatPolicy(
        "xlsx",
        frozenset(
            {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        ),
        10 * _MIB,
    ),
    ".json": FormatPolicy("faq", frozenset({"application/json"}), 5 * _MIB),
}


def _safe_name(file_name: str) -> str:
    normalized = unicodedata.normalize("NFC", file_name.strip())
    if (
        not normalized
        or normalized in {".", ".."}
        or PurePath(normalized).name != normalized
        or "/" in normalized
        or "\\" in normalized
        or any(unicodedata.category(char) in {"Cc", "Cf"} for char in normalized)
    ):
        raise IngestionValidationError("file_name_invalid", "File name is invalid.")
    if len(normalized) > 255:
        raise IngestionValidationError("file_name_invalid", "File name is too long.")
    return normalized


def _validate_office_archive(content: bytes, source_type: str) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as bundle:
            entries = bundle.infolist()
            if len(entries) > 2_000:
                raise IngestionValidationError(
                    "archive_entry_limit", "Office file has too many entries."
                )
            total = 0
            expected = (
                "word/document.xml" if source_type == "docx" else "xl/workbook.xml"
            )
            names = {entry.filename for entry in entries}
            if expected not in names:
                raise IngestionValidationError(
                    "media_type_mismatch",
                    "Office file structure does not match its extension.",
                )
            for entry in entries:
                lowered = entry.filename.casefold()
                if lowered.endswith((".zip", ".docx", ".xlsx")):
                    raise IngestionValidationError(
                        "nested_archive_forbidden", "Nested archives are not supported."
                    )
                if "vbaproject.bin" in lowered or lowered.endswith(".bin"):
                    raise IngestionValidationError(
                        "office_macro_forbidden",
                        "Macro-enabled Office files are not supported.",
                    )
                total += entry.file_size
                ratio = entry.file_size / max(1, entry.compress_size)
                if ratio > 100:
                    raise IngestionValidationError(
                        "archive_ratio_exceeded",
                        "Office file compression ratio is unsafe.",
                    )
                if entry.file_size > 10 * _MIB:
                    raise IngestionValidationError(
                        "archive_entry_too_large",
                        "Office file contains an oversized entry.",
                    )
            if total > 50 * _MIB:
                raise IngestionValidationError(
                    "archive_expanded_too_large",
                    "Office file expands beyond the safe limit.",
                )
    except zipfile.BadZipFile as exc:
        raise IngestionValidationError(
            "media_type_mismatch", "Office file is malformed."
        ) from exc


def validate_upload(file_name: str, media_type: str, content: bytes) -> ValidatedUpload:
    display_name = _safe_name(file_name)
    suffix = PurePath(display_name).suffix.casefold()
    policy = FORMAT_POLICIES.get(suffix)
    if policy is None:
        raise IngestionValidationError(
            "unsupported_format", "This file format is not supported."
        )
    normalized_media = media_type.split(";", 1)[0].strip().casefold()
    if normalized_media not in policy.media_types:
        raise IngestionValidationError(
            "media_type_mismatch", "Content type does not match the file extension."
        )
    if len(content) > policy.max_bytes:
        raise IngestionValidationError(
            "file_too_large", "File exceeds the supported size limit."
        )
    if not content:
        raise IngestionValidationError("file_empty", "File is empty.")
    if policy.source_type == "pdf" and not content.startswith(b"%PDF-"):
        raise IngestionValidationError(
            "media_type_mismatch", "PDF signature is missing."
        )
    if policy.source_type in {"docx", "xlsx"}:
        if not content.startswith(b"PK"):
            raise IngestionValidationError(
                "media_type_mismatch", "Office file signature is missing."
            )
        _validate_office_archive(content, policy.source_type)
    if policy.source_type in {"txt", "markdown", "csv"} and b"\x00" in content:
        raise IngestionValidationError(
            "binary_text", "Binary content is not accepted as text."
        )
    return ValidatedUpload(
        display_name=display_name,
        source_type=policy.source_type,
        media_type=normalized_media,
        byte_count=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
    )
