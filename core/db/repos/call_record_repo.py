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
        """Idempotent save for CallRecord (ON CONFLICT (call_id) DO NOTHING)."""
        self._records[record.call_id] = record
        if self.db_pool:
            try:
                import json

                turns_json = json.dumps([t.to_dict() if hasattr(t, "to_dict") else t for t in record.turns])
                async with self.db_pool.acquire() as conn:
                    await conn.execute("SET LOCAL app.current_tenant_id = $1", str(record.tenant_id))
                    await conn.execute(
                        """
                        INSERT INTO call_records (
                            call_id, tenant_id, agent_id, session_id, caller_id,
                            started_at, ended_at, compliance_tier, turns_jsonb
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                        ON CONFLICT (call_id) DO NOTHING
                        """,
                        record.call_id,
                        record.tenant_id,
                        record.agent_id,
                        record.session_id,
                        record.caller_id,
                        record.started_at,
                        record.ended_at,
                        record.compliance_tier,
                        turns_json,
                    )
            except Exception:
                pass
        return record

    async def get_by_id(self, call_id: UUID) -> CallRecord | None:
        """Fetch CallRecord by call_id."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM call_records WHERE call_id = $1", call_id
                    )
                    if row:
                        return CallRecord(
                            call_id=row["call_id"],
                            tenant_id=row["tenant_id"],
                            agent_id=row["agent_id"],
                            session_id=row["session_id"],
                            caller_id=row["caller_id"],
                            compliance_tier=row["compliance_tier"],
                            started_at=row["started_at"],
                            ended_at=row["ended_at"],
                        )
            except Exception:
                pass
        return self._records.get(call_id)

    async def get_by_session_id(self, session_id: UUID) -> CallRecord | None:
        """Fetch CallRecord by session_id."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM call_records WHERE session_id = $1", session_id
                    )
                    if row:
                        return CallRecord(
                            call_id=row["call_id"],
                            tenant_id=row["tenant_id"],
                            agent_id=row["agent_id"],
                            session_id=row["session_id"],
                            caller_id=row["caller_id"],
                            compliance_tier=row["compliance_tier"],
                            started_at=row["started_at"],
                            ended_at=row["ended_at"],
                        )
            except Exception:
                pass
        for rec in self._records.values():
            if rec.session_id == session_id:
                return rec
        return None
