"""Error-detail privacy and credential redaction."""

from __future__ import annotations

from typing import Any

from core.compliance.redaction import redact_sensitive_data


def redact_error_details(details: dict[str, Any]) -> dict[str, Any]:
    """Return recursively sanitized error details, including nested sequences."""
    redacted = redact_sensitive_data(details)
    if not isinstance(redacted, dict):
        raise TypeError("Error detail redaction must preserve the mapping.")
    return redacted
