"""UCVE Redaction Policy Model."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RedactionPolicy:
    """Policy rules governing transcript redaction and retention."""

    redact_pii_in_transcript: bool = True
    pii_categories: list[str] = field(default_factory=lambda: ["phone", "email", "ssn"])
    allowlist_fields: list[str] = field(default_factory=list)
    zero_retention_mode: bool = False
    retention_days: int = 90
