"""Durable idempotent usage ledger and quota snapshots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from core.db.async_pg import AsyncDatabase, get_default_database
from core.db.models import UsageEvent


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    tenant_id: str
    max_concurrent: int
    monthly_seconds_limit: float
    monthly_seconds_used: float
    max_llm_tokens_month: int
    monthly_llm_tokens: float
    soft_cap_percent: int
    hard_cap_percent: int
    totals: dict[str, float]


class PostgresUsageRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def record_usage(self, tenant_id: str, event: UsageEvent) -> bool:
        if event.tenant_id != tenant_id:
            raise PermissionError("UsageEvent tenant_id mismatch with query context.")
        event_key = event.event_key or f"{event.id}:{event.usage_kind}"
        async with self.database.tenant_transaction(tenant_id) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO usage_events (
                    id, event_key, tenant_id, session_id, usage_kind, quantity,
                    unit, provider_id, provider_request_id, metadata, recorded_at
                ) VALUES (
                    %s::uuid, %s, %s::uuid, %s::uuid, %s, %s,
                    %s, %s, %s, %s::jsonb, %s
                )
                ON CONFLICT (tenant_id, event_key) DO NOTHING
                RETURNING id
                """,
                (
                    event.id,
                    event_key,
                    tenant_id,
                    event.session_id,
                    event.usage_kind,
                    event.quantity,
                    event.unit,
                    event.provider_id,
                    event.provider_request_id,
                    json.dumps(event.metadata),
                    event.recorded_at,
                ),
            )
            return await cursor.fetchone() is not None

    async def get_usage_snapshot(self, tenant_id: str) -> UsageSnapshot:
        async with self.database.tenant_transaction(tenant_id) as connection:
            quota_cursor = await connection.execute(
                "SELECT max_concurrent_sessions, monthly_seconds_limit, "
                "max_llm_tokens_month, soft_cap_percent, hard_cap_percent "
                "FROM quota_state WHERE tenant_id = %s::uuid",
                (tenant_id,),
            )
            quota = await quota_cursor.fetchone()
            totals_cursor = await connection.execute(
                "SELECT usage_kind, COALESCE(SUM(quantity), 0)::float8 "
                "FROM usage_events WHERE tenant_id = %s::uuid "
                "AND recorded_at >= date_trunc('month', NOW()) "
                "GROUP BY usage_kind",
                (tenant_id,),
            )
            total_rows = await totals_cursor.fetchall()
        totals = {str(row[0]): float(row[1]) for row in total_rows}
        max_concurrent, seconds_limit, token_limit, soft_cap, hard_cap = quota or (
            10,
            36000.0,
            1_000_000,
            80,
            100,
        )
        return UsageSnapshot(
            tenant_id=tenant_id,
            max_concurrent=int(max_concurrent),
            monthly_seconds_limit=float(seconds_limit),
            monthly_seconds_used=float(totals.get("agent_sec", 0.0)),
            max_llm_tokens_month=int(token_limit),
            monthly_llm_tokens=float(totals.get("llm_tokens", 0.0)),
            soft_cap_percent=int(soft_cap),
            hard_cap_percent=int(hard_cap),
            totals=totals,
        )


def build_usage_repository() -> PostgresUsageRepository | None:
    from core.db.pg import use_memory_repos

    return None if use_memory_repos() else PostgresUsageRepository()
