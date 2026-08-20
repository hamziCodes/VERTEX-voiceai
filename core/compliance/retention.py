"""UCVE Retention Scheduler & Automated Data Purge Engine."""

from __future__ import annotations

import datetime
from typing import Any, Callable

from core.compliance.legal_hold import LegalHoldManager


class RetentionScheduler:
    """Retention scheduler calculating purge timestamps and executing automated cleanup."""

    def __init__(self, legal_hold_mgr: LegalHoldManager | None = None) -> None:
        self.legal_hold_mgr = legal_hold_mgr or LegalHoldManager()
        self._deleted_ids: list[str] = []

    def calculate_purge_after(
        self, started_at: datetime.datetime, retention_days: int = 90
    ) -> datetime.datetime:
        """Calculate purge_after timestamp for session."""
        return started_at + datetime.timedelta(days=retention_days)

    def purge_expired_sessions(
        self,
        expired_sessions: list[dict[str, Any]],
        s3_client: Any = None,
        delete_session: Callable[[str], None] | None = None,
    ) -> int:
        """Purge expired session records and associated S3 audio if not under legal hold."""
        purged_count = 0
        for session in expired_sessions:
            session_id = session.get("session_id") or session.get("id")
            if not session_id:
                continue
            if session.get("legal_hold") or self.legal_hold_mgr.is_legal_hold(session_id):
                continue

            s3_uri = session.get("s3_uri")
            if s3_uri and s3_client is not None:
                deleter = getattr(s3_client, "delete_object", None) or getattr(
                    s3_client, "delete", None
                )
                if deleter is None:
                    continue  # cannot claim purge without storage delete
                deleter(s3_uri)

            if delete_session is not None:
                delete_session(session_id)
            self._deleted_ids.append(session_id)
            purged_count += 1

        return purged_count

    def load_expired_from_rows(
        self, rows: list[dict[str, Any]], now: datetime.datetime | None = None
    ) -> list[dict[str, Any]]:
        """Filter DB rows to those with purge_after <= now and legal_hold false."""
        now = now or datetime.datetime.now(datetime.timezone.utc)
        expired: list[dict[str, Any]] = []
        for row in rows:
            purge_after = row.get("purge_after")
            if purge_after is None:
                continue
            if row.get("legal_hold"):
                continue
            if purge_after <= now:
                expired.append(row)
        return expired
