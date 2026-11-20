"""Retention scheduling and fail-closed session purge contracts."""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from core.compliance.legal_hold import LegalHoldManager


class PurgeStatus(StrEnum):
    PURGED = "purged"
    HELD = "held"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PurgeOutcome:
    """Safe evidence for one retention candidate; never contains exception text."""

    session_id: str
    status: PurgeStatus
    reason: str | None = None
    object_deleted: bool = False
    record_deleted: bool = False


class RetentionScheduler:
    """Calculate expiry and purge records only after required deletion succeeds."""

    def __init__(self, legal_hold_mgr: LegalHoldManager | None = None) -> None:
        self.legal_hold_mgr = legal_hold_mgr or LegalHoldManager()
        self._deleted_ids: list[str] = []
        self.last_outcomes: tuple[PurgeOutcome, ...] = ()

    @staticmethod
    def _require_aware(value: datetime.datetime, field: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field} must be timezone-aware.")

    def calculate_purge_after(
        self, started_at: datetime.datetime, retention_days: int = 90
    ) -> datetime.datetime:
        """Calculate an aware purge timestamp from a non-negative retention."""
        self._require_aware(started_at, "started_at")
        if retention_days < 0:
            raise ValueError("retention_days must be non-negative.")
        return started_at + datetime.timedelta(days=retention_days)

    def _is_held(self, session: dict[str, Any], session_id: str) -> bool:
        return bool(session.get("legal_hold")) or self.legal_hold_mgr.is_legal_hold(
            session_id
        )

    @staticmethod
    def _object_reference(session: dict[str, Any]) -> str | None:
        value = session.get("recording_s3_uri") or session.get("s3_uri")
        return str(value) if value else None

    def purge_expired_sessions(
        self,
        expired_sessions: list[dict[str, Any]],
        s3_client: Any = None,
        delete_session: Callable[[str], Any] | None = None,
    ) -> int:
        """Purge candidates and publish safe per-item outcomes.

        Object deletion happens before record deletion so a missing object-store
        capability cannot orphan an undeleted recording. Any exception or an
        explicit ``False`` result fails the candidate. A missing record callback
        uses the scheduler's in-memory fixture ledger for legacy unit tests.
        """
        outcomes: list[PurgeOutcome] = []
        for session in expired_sessions:
            raw_session_id = session.get("session_id") or session.get("id")
            if not raw_session_id:
                outcomes.append(
                    PurgeOutcome("", PurgeStatus.SKIPPED, reason="missing_session_id")
                )
                continue
            session_id = str(raw_session_id)
            if session_id in self._deleted_ids:
                outcomes.append(
                    PurgeOutcome(
                        session_id, PurgeStatus.SKIPPED, reason="already_purged"
                    )
                )
                continue
            if self._is_held(session, session_id):
                outcomes.append(
                    PurgeOutcome(session_id, PurgeStatus.HELD, reason="legal_hold")
                )
                continue

            reference = self._object_reference(session)
            object_deleted = False
            if reference is not None:
                if s3_client is None:
                    outcomes.append(
                        PurgeOutcome(
                            session_id,
                            PurgeStatus.FAILED,
                            reason="object_store_unavailable",
                        )
                    )
                    continue
                deleter = getattr(s3_client, "delete", None) or getattr(
                    s3_client, "delete_object", None
                )
                if deleter is None:
                    outcomes.append(
                        PurgeOutcome(
                            session_id,
                            PurgeStatus.FAILED,
                            reason="object_delete_unsupported",
                        )
                    )
                    continue
                try:
                    result = deleter(reference)
                except Exception:
                    outcomes.append(
                        PurgeOutcome(
                            session_id,
                            PurgeStatus.FAILED,
                            reason="object_delete_failed",
                        )
                    )
                    continue
                if result is False:
                    outcomes.append(
                        PurgeOutcome(
                            session_id,
                            PurgeStatus.FAILED,
                            reason="object_delete_failed",
                        )
                    )
                    continue
                object_deleted = True

            # Recheck before the database layer so a newly applied hold stops it.
            if self._is_held(session, session_id):
                outcomes.append(
                    PurgeOutcome(
                        session_id,
                        PurgeStatus.FAILED,
                        reason="legal_hold_applied_during_purge",
                        object_deleted=object_deleted,
                    )
                )
                continue

            try:
                record_result = (
                    delete_session(session_id) if delete_session is not None else True
                )
            except Exception:
                outcomes.append(
                    PurgeOutcome(
                        session_id,
                        PurgeStatus.FAILED,
                        reason="record_delete_failed",
                        object_deleted=object_deleted,
                    )
                )
                continue
            if record_result is False:
                outcomes.append(
                    PurgeOutcome(
                        session_id,
                        PurgeStatus.FAILED,
                        reason="record_delete_failed",
                        object_deleted=object_deleted,
                    )
                )
                continue

            self._deleted_ids.append(session_id)
            outcomes.append(
                PurgeOutcome(
                    session_id,
                    PurgeStatus.PURGED,
                    object_deleted=object_deleted,
                    record_deleted=True,
                )
            )

        self.last_outcomes = tuple(outcomes)
        return sum(outcome.status is PurgeStatus.PURGED for outcome in outcomes)

    def load_expired_from_rows(
        self, rows: list[dict[str, Any]], now: datetime.datetime | None = None
    ) -> list[dict[str, Any]]:
        """Filter rows to aware, expired, non-held retention candidates."""
        now = now or datetime.datetime.now(datetime.UTC)
        self._require_aware(now, "now")
        expired: list[dict[str, Any]] = []
        for row in rows:
            purge_after = row.get("purge_after")
            if purge_after is None:
                continue
            if not isinstance(purge_after, datetime.datetime):
                raise TypeError("purge_after must be a datetime.")
            self._require_aware(purge_after, "purge_after")
            session_id = str(row.get("session_id") or row.get("id") or "")
            if row.get("legal_hold") or (
                session_id and self.legal_hold_mgr.is_legal_hold(session_id)
            ):
                continue
            if purge_after <= now:
                expired.append(row)
        return expired
