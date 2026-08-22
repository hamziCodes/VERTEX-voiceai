"""Error Details PHI & Credentials Redactor."""

from __future__ import annotations

from typing import Any

SENSITIVE_KEYS = {"token", "secret", "password", "ssn", "dob", "transcript", "audio_data", "phi"}


def redact_error_details(details: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive keys from error details dictionary."""
    redacted = {}
    for k, v in details.items():
        if k.lower() in SENSITIVE_KEYS:
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = redact_error_details(v)
        else:
            redacted[k] = v
    return redacted
