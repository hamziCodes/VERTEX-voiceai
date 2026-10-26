from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.compliance.legal_hold import LegalHoldManager
from core.compliance.redaction import RedactionService, redact_sensitive_data
from core.compliance.redaction_policy import RedactionPolicy
from core.compliance.retention import PurgeStatus, RetentionScheduler
from core.errors.redaction import redact_error_details
from core.observability.logging import StructuredJSONFormatter


def test_recursive_redaction_covers_nested_values_sensitive_keys_and_binary() -> None:
    source: dict[str, Any] = {
        "safe": "reference-123",
        "nested": {
            "contacts": [
                "Call +1 (555) 123-4567",
                {"email": "person@example.com", "note": "SSN 123-45-6789"},
            ],
            "credentials": {"apiKey": "key-value", "authorization": "Bearer value"},
            "transcript_preview": "private words",
            "vendor_response_body": {"raw": "private vendor output"},
            "audio_data": b"raw-audio",
        },
    }

    redacted = redact_sensitive_data(source)

    rendered = json.dumps(redacted)
    assert redacted["safe"] == "reference-123"
    assert "555" not in rendered
    assert "person@example.com" not in rendered
    assert "123-45-6789" not in rendered
    assert "key-value" not in rendered
    assert "Bearer value" not in rendered
    assert "private words" not in rendered
    assert "private vendor output" not in rendered
    assert "raw-audio" not in rendered
    assert source["nested"]["transcript_preview"] == "private words"


def test_transcript_redaction_recurses_without_mutating_turns() -> None:
    turns = [
        {
            "speaker": "user",
            "text": "Email me at person@example.com",
            "metadata": {
                "tool": {"phone": "+15551234567"},
                "alternatives": ["SSN 123-45-6789"],
            },
        }
    ]

    result = RedactionService().redact_transcript(turns, RedactionPolicy())

    rendered = json.dumps(result)
    assert "person@example.com" not in rendered
    assert "+15551234567" not in rendered
    assert "123-45-6789" not in rendered
    assert turns[0]["text"] == "Email me at person@example.com"


def test_structured_formatter_sanitizes_nested_extra_fields() -> None:
    record = logging.LogRecord(
        name="privacy-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Provider failed for person@example.com",
        args=(),
        exc_info=None,
    )
    record.extra_fields = {  # type: ignore[attr-defined]
        "provider": {
            "response_body": "customer said call +15551234567",
            "safe_status": 502,
        },
        "attempt": [{"token": "secret-token"}],
    }

    payload = json.loads(StructuredJSONFormatter().format(record))
    rendered = json.dumps(payload)

    assert payload["provider"]["safe_status"] == 502
    assert "person@example.com" not in rendered
    assert "+15551234567" not in rendered
    assert "secret-token" not in rendered


def test_error_redaction_recurses_through_lists() -> None:
    result = redact_error_details(
        {
            "failures": [
                {"password": "do-not-log", "reason": "Call +15551234567"},
                "person@example.com",
            ]
        }
    )
    rendered = json.dumps(result)
    assert "do-not-log" not in rendered
    assert "+15551234567" not in rendered
    assert "person@example.com" not in rendered


def test_retention_requires_timezone_aware_start_and_nonnegative_days() -> None:
    scheduler = RetentionScheduler()
    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.calculate_purge_after(datetime(2026, 1, 1), retention_days=30)
    with pytest.raises(ValueError, match="non-negative"):
        scheduler.calculate_purge_after(
            datetime(2026, 1, 1, tzinfo=UTC), retention_days=-1
        )


def test_legal_hold_blocks_object_and_record_deletion() -> None:
    hold = LegalHoldManager()
    hold.set_legal_hold("held-session")
    scheduler = RetentionScheduler(hold)
    deleted_objects: list[str] = []
    deleted_records: list[str] = []

    class Store:
        def delete(self, reference: str) -> None:
            deleted_objects.append(reference)

    count = scheduler.purge_expired_sessions(
        [
            {
                "session_id": "held-session",
                "recording_s3_uri": "s3://recordings/held.wav",
            }
        ],
        s3_client=Store(),
        delete_session=lambda session_id: deleted_records.append(session_id),
    )

    assert count == 0
    assert deleted_objects == []
    assert deleted_records == []
    assert scheduler.last_outcomes[0].status is PurgeStatus.HELD


def test_retention_does_not_delete_record_when_object_delete_fails() -> None:
    scheduler = RetentionScheduler()
    deleted_records: list[str] = []

    class FailingStore:
        def delete(self, _reference: str) -> None:
            raise OSError("storage detail that must not escape")

    count = scheduler.purge_expired_sessions(
        [
            {
                "session_id": "failed-object",
                "recording_s3_uri": "s3://recordings/failure.wav",
            }
        ],
        s3_client=FailingStore(),
        delete_session=lambda session_id: deleted_records.append(session_id),
    )

    assert count == 0
    assert deleted_records == []
    outcome = scheduler.last_outcomes[0]
    assert outcome.status is PurgeStatus.FAILED
    assert outcome.reason == "object_delete_failed"
    assert "storage detail" not in repr(outcome)


def test_retention_requires_record_delete_confirmation() -> None:
    scheduler = RetentionScheduler()

    count = scheduler.purge_expired_sessions(
        [{"session_id": "db-failure"}],
        delete_session=lambda _session_id: False,
    )

    assert count == 0
    assert scheduler.last_outcomes[0].status is PurgeStatus.FAILED
    assert scheduler.last_outcomes[0].reason == "record_delete_failed"


def test_retention_reports_success_only_after_required_deletions() -> None:
    scheduler = RetentionScheduler()
    deleted_objects: list[str] = []
    deleted_records: list[str] = []

    class Store:
        def delete(self, reference: str) -> bool:
            deleted_objects.append(reference)
            return True

    count = scheduler.purge_expired_sessions(
        [
            {
                "session_id": "expired-session",
                "recording_s3_uri": "s3://recordings/expired.wav",
            }
        ],
        s3_client=Store(),
        delete_session=lambda session_id: deleted_records.append(session_id) or True,
    )

    assert count == 1
    assert deleted_objects == ["s3://recordings/expired.wav"]
    assert deleted_records == ["expired-session"]
    outcome = scheduler.last_outcomes[0]
    assert outcome.status is PurgeStatus.PURGED
    assert outcome.object_deleted is True
    assert outcome.record_deleted is True


def test_expiry_filter_rejects_naive_timestamps_and_holds() -> None:
    scheduler = RetentionScheduler()
    now = datetime(2026, 1, 2, tzinfo=UTC)
    rows = [
        {"session_id": "expired", "purge_after": now - timedelta(seconds=1)},
        {"session_id": "future", "purge_after": now + timedelta(seconds=1)},
        {
            "session_id": "held",
            "purge_after": now - timedelta(seconds=1),
            "legal_hold": True,
        },
    ]
    assert scheduler.load_expired_from_rows(rows, now=now) == [rows[0]]

    with pytest.raises(ValueError, match="timezone-aware"):
        scheduler.load_expired_from_rows(
            [{"session_id": "naive", "purge_after": datetime(2026, 1, 1)}],
            now=now,
        )
