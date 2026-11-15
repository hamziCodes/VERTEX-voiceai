"""Phase 14: logs carry no PII, credentials or conversation content."""

from __future__ import annotations

import io
import json
import logging

import pytest

from core.compliance.redaction import RedactionService, redact_log_fields, redact_text
from core.compliance.redaction_policy import RedactionPolicy
from core.observability.logging import (
    StructuredJSONFormatter,
    get_logger,
    install_log_redaction,
)


@pytest.mark.parametrize(
    ("raw", "leaked"),
    [
        ("card 4111 1111 1111 1111 on file", "4111 1111 1111 1111"),
        ("card 5500-0000-0000-0004", "5500-0000-0000-0004"),
        ("IBAN GB82 WEST 1234 5698 7654 32", "GB82 WEST"),
        ("IBAN PK36SCBL0000001123456702", "PK36SCBL0000001123456702"),
        ("CNIC 35202-1234567-1", "35202-1234567"),
        ("Emirates ID 784-1987-1234567-1", "784-1987-1234567"),
        ("MyKad 900101-14-5678", "900101-14-5678"),
        ("Aadhaar 1234 5678 9012", "1234 5678 9012"),
        ("NI number AB 12 34 56 C", "AB 12 34 56 C"),
        ("UK mobile +44 7700 900123", "7700 900123"),
        ("Pakistan +92 300 1234567", "300 1234567"),
        ("UAE +971 50 123 4567", "50 123 4567"),
        ("Malaysia +60 12-345 6789", "345 6789"),
        ("Urdu digits ۰۳۰۰۱۲۳۴۵۶۷", "۰۳۰۰۱۲۳۴۵۶۷"),
        ("Arabic digits ٠٥٠١٢٣٤٥٦٧", "٠٥٠١٢٣٤٥٦٧"),
        ("mail someone@example.co.uk", "someone@example.co.uk"),
        ("wss://x/ws?token=abc.def&rate=16000", "abc.def"),
    ],
)
def test_international_pii_is_redacted(raw: str, leaked: str) -> None:
    assert leaked not in redact_text(raw)


def test_ordinary_numbers_survive() -> None:
    text = "order 12345 for 3 items at 14:30 on 2026-11-15, room 404"
    assert redact_text(text) == text


def test_log_fields_drop_content_and_secrets_at_any_depth() -> None:
    cleaned = redact_log_fields(
        {
            "provider": "gladia",
            "attempt": 2,
            "response": {
                "body": "caller said: my number is +44 7700 900123",
                "headers": [{"x-api-key": "sk_live_abc"}, {"content-type": "json"}],
                "nested": {"deeper": {"prompt": "system prompt", "text": "hello"}},
            },
            "turns": [{"utterance": "hi", "speaker": "user"}],
        }
    )
    dumped = json.dumps(cleaned)
    for secret in ("7700", "sk_live_abc", "system prompt", '"hello"', '"hi"'):
        assert secret not in dumped
    assert cleaned["provider"] == "gladia"
    assert cleaned["attempt"] == 2
    assert cleaned["turns"][0]["speaker"] == "user"


def test_transcript_redaction_keeps_turn_text_but_scrubs_pii() -> None:
    turns = [{"speaker": "user", "text": "call me on +44 7700 900123 please"}]
    redacted = RedactionService().redact_transcript(turns, RedactionPolicy())
    assert redacted[0]["text"].startswith("call me on")
    assert "7700" not in redacted[0]["text"]


def test_stdlib_loggers_are_redacted_process_wide() -> None:
    install_log_redaction()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger("third.party.library")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("caller %s paid with %s", "+971 50 123 4567", "4111 1111 1111 1111")
        try:
            raise ValueError("lookup failed for someone@example.com")
        except ValueError:
            logger.exception("provider call failed")
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert "50 123 4567" not in output
    assert "4111" not in output
    assert "someone@example.com" not in output
    assert "ValueError" in output  # the traceback survives, minus the PII


def test_structured_logger_removes_content_fields() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJSONFormatter())
    wrapped = get_logger("wavia.test.content")
    raw_logger = logging.getLogger("wavia.test.content")
    raw_logger.handlers = [handler]
    wrapped.info("turn complete", text="my card is 4111 1111 1111 1111", text_chars=30)
    record = json.loads(stream.getvalue().strip().splitlines()[-1])
    assert record["text"] == "[REDACTED]"
    assert record["text_chars"] == 30


def test_adapters_no_longer_log_transcript_or_speech_previews() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "core" / "providers" / "adapters"
    gladia = (root / "gladia_live_stt.py").read_text(encoding="utf-8")
    cartesia = (root / "cartesia_tts.py").read_text(encoding="utf-8")
    assert "text=text[" not in gladia
    assert "payload=data" not in gladia
    assert "preview=" not in cartesia
