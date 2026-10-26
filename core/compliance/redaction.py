"""Recursive privacy redaction for transcripts, logs, and error payloads."""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from core.compliance.redaction_policy import RedactionPolicy

REDACTED = "[REDACTED]"
REDACTED_BINARY = "[REDACTED_BINARY]"
REDACTED_DEPTH = "[REDACTED_DEPTH]"

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d(?:[\s().-]*\d){9,14}(?!\w)")
_AUTH_PARAM_PATTERN = re.compile(
    r"((?:token|api_key|signature|access_token|jwt)=)[^&\s]*", re.IGNORECASE
)

_SENSITIVE_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "audiodata",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "dob",
        "email",
        "hmacsecret",
        "password",
        "phi",
        "rawresponse",
        "refreshtoken",
        "responsebody",
        "secret",
        "setcookie",
        "ssn",
        "token",
        "transcript",
        "transcriptpreview",
        "vendorresponse",
        "vendorresponsebody",
    }
)


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).casefold())


def redact_text(text: str) -> str:
    """Remove supported PII and authentication query values from text."""
    cleaned = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    cleaned = _SSN_PATTERN.sub("[REDACTED_SSN]", cleaned)
    cleaned = _PHONE_PATTERN.sub("[REDACTED_PHONE]", cleaned)
    return _AUTH_PARAM_PATTERN.sub(r"\1[REDACTED]", cleaned)


def redact_sensitive_data(
    value: Any,
    *,
    allowlist_fields: Sequence[str] = (),
    max_depth: int = 12,
    _depth: int = 0,
) -> Any:
    """Return a sanitized copy of nested JSON-like data.

    Sensitive keys are removed before their values are inspected. Strings are
    scrubbed for supported PII and authentication query values. Binary payloads
    are never rendered. The depth bound prevents hostile cyclic/deep objects
    from consuming unbounded stack in a logging path.
    """
    if _depth > max_depth:
        return REDACTED_DEPTH
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED_BINARY
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        allowed = {_normalized_key(field) for field in allowlist_fields}
        result: dict[Any, Any] = {}
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in _SENSITIVE_KEYS and normalized not in allowed:
                result[key] = REDACTED
            else:
                result[key] = redact_sensitive_data(
                    item,
                    allowlist_fields=allowlist_fields,
                    max_depth=max_depth,
                    _depth=_depth + 1,
                )
        return result
    if isinstance(value, tuple):
        return tuple(
            redact_sensitive_data(
                item,
                allowlist_fields=allowlist_fields,
                max_depth=max_depth,
                _depth=_depth + 1,
            )
            for item in value
        )
    if isinstance(value, list):
        return [
            redact_sensitive_data(
                item,
                allowlist_fields=allowlist_fields,
                max_depth=max_depth,
                _depth=_depth + 1,
            )
            for item in value
        ]
    if isinstance(value, (set, frozenset)):
        return [
            redact_sensitive_data(
                item,
                allowlist_fields=allowlist_fields,
                max_depth=max_depth,
                _depth=_depth + 1,
            )
            for item in value
        ]
    return value


class RedactionService:
    """Apply privacy policy to conversation transcript structures."""

    def redact_transcript(
        self, turns: list[dict[str, Any]], policy: RedactionPolicy
    ) -> list[dict[str, Any]]:
        """Return a recursively sanitized copy of transcript turns."""
        if not policy.redact_pii_in_transcript:
            return copy.deepcopy(turns)
        redacted = redact_sensitive_data(
            turns,
            allowlist_fields=policy.allowlist_fields,
        )
        if not isinstance(redacted, list):
            raise TypeError("Transcript redaction must preserve the turn list.")
        return redacted
