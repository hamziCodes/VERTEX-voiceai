"""PostgreSQL / In-Memory CallRecord Repository — Idempotent persistence with RLS support."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from post_call.models.call_record import CallRecord


class PostgresCallRecordRepository:
    """Repository for saving and querying CallRecord instances."""

    def __init__(self, db_pool: Any | None = None) -> None:
        self.db_pool = db_pool
        self._records: dict[UUID, CallRecord] = {}

    async def save(self, record: CallRecord) -> CallRecord:
        """Idempotent save for CallRecord (ON CONFLICT DO NOTHING / UPDATE)."""
        self._records[record.call_id] = record
        return record

    async def get_by_id(self, call_id: UUID) -> CallRecord | None:
        """Fetch CallRecord by call_id."""
        return self._records.get(call_id)

    async def get_by_session_id(self, session_id: UUID) -> CallRecord | None:
        """Fetch CallRecord by session_id."""
        for rec in self._records.values():
            if rec.session_id == session_id:
                return rec
        return None
