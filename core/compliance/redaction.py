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
# Python's \d matches every Unicode decimal digit, so the numeric patterns
# below also cover Arabic-Indic and Extended Arabic-Indic digits used in
# Arabic and Urdu text.
_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")
_CARD_CANDIDATE = re.compile(r"(?<!\w)\d(?:[ -]?\d){12,18}(?!\w)")
_NATIONAL_ID_PATTERNS = (
    re.compile(r"\b\d{5}-\d{7}-\d\b"),  # Pakistan CNIC
    re.compile(r"\b784-?\d{4}-?\d{7}-?\d\b"),  # UAE Emirates ID
    re.compile(r"\b\d{6}-\d{2}-\d{4}\b"),  # Malaysia MyKad NRIC
    re.compile(r"\b\d{4}[ -]\d{4}[ -]\d{4}\b"),  # India Aadhaar (grouped)
    re.compile(  # UK National Insurance number
        r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]"
        r" ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b",
        re.IGNORECASE,
    ),
)
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


def _luhn_valid(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact_card(match: re.Match[str]) -> str:
    digits = "".join(str(int(ch)) for ch in match.group(0) if ch.isdigit())
    if 13 <= len(digits) <= 19 and _luhn_valid(digits):
        return "[REDACTED_CARD]"
    return match.group(0)


def redact_text(text: str) -> str:
    """Remove supported PII and authentication query values from text.

    Covers email addresses, payment card numbers (Luhn-checked), IBANs, US SSNs,
    Pakistani CNIC, UAE Emirates ID, Malaysian NRIC, grouped Indian Aadhaar,
    UK National Insurance numbers, international phone numbers (10-15 digits,
    any Unicode digit script) and authentication query parameters. Names and
    street addresses cannot be detected reliably by pattern and are not
    claimed; content fields are removed by key instead.
    """
    cleaned = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    cleaned = _IBAN_PATTERN.sub("[REDACTED_IBAN]", cleaned)
    # Emirates IDs (784-...) can pass the Luhn check; label them as IDs first.
    cleaned = _NATIONAL_ID_PATTERNS[1].sub("[REDACTED_ID]", cleaned)
    cleaned = _CARD_CANDIDATE.sub(_redact_card, cleaned)
    cleaned = _SSN_PATTERN.sub("[REDACTED_SSN]", cleaned)
    for pattern in _NATIONAL_ID_PATTERNS:
        cleaned = pattern.sub("[REDACTED_ID]", cleaned)
    cleaned = _PHONE_PATTERN.sub("[REDACTED_PHONE]", cleaned)
    return _AUTH_PARAM_PATTERN.sub(r"\1[REDACTED]", cleaned)


# Log records must not carry conversation or provider content at all, so the
# logging path removes these keys entirely (in addition to _SENSITIVE_KEYS).
# Transcript redaction keeps them and scrubs their text instead.
_LOG_CONTENT_KEYS = frozenset(
    {
        "apikeyvalue",
        "bearer",
        "body",
        "content",
        "greeting",
        "messages",
        "payload",
        "preview",
        "prompt",
        "rawbody",
        "requestbody",
        "systemprompt",
        "text",
        "usertext",
        "utterance",
        "xapikey",
    }
)


def redact_log_fields(value: Any) -> Any:
    """Sanitize structured log fields: secrets and content keys removed."""
    return redact_sensitive_data(value, _extra_keys=_LOG_CONTENT_KEYS)


def redact_sensitive_data(
    value: Any,
    *,
    allowlist_fields: Sequence[str] = (),
    max_depth: int = 12,
    _depth: int = 0,
    _extra_keys: frozenset[str] = frozenset(),
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
            sensitive = normalized in _SENSITIVE_KEYS or normalized in _extra_keys
            if sensitive and normalized not in allowed:
                result[key] = REDACTED
            else:
                result[key] = redact_sensitive_data(
                    item,
                    allowlist_fields=allowlist_fields,
                    max_depth=max_depth,
                    _depth=_depth + 1,
                    _extra_keys=_extra_keys,
                )
        return result
    if isinstance(value, tuple):
        return tuple(
            redact_sensitive_data(
                item,
                allowlist_fields=allowlist_fields,
                max_depth=max_depth,
                _depth=_depth + 1,
                _extra_keys=_extra_keys,
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
                _extra_keys=_extra_keys,
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
                _extra_keys=_extra_keys,
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
