"""Alert storage: in-memory for development/tests, PostgreSQL in deployments."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from core.alerts.models import SEVERITY_RANK, Alert, AlertCode, AlertSeverity

MAX_LIST_LIMIT = 200


class AlertRepository(Protocol):
    async def upsert_open(
        self,
        *,
        alert_key: str,
        code: AlertCode,
        severity: AlertSeverity,
        tenant_id: UUID | None,
        summary: str,
        facts: dict[str, Any],
    ) -> tuple[Alert, bool, bool]: ...

    async def resolve(self, alert_key: str, *, resolved_by: str) -> Alert | None: ...

    async def resolve_by_id(
        self, alert_id: UUID, *, resolved_by: str
    ) -> Alert | None: ...

    async def set_delivery(self, alert_id: UUID, status: str) -> None: ...

    async def list_alerts(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Alert]: ...

    async def list_tenant_alerts(
        self, tenant_id: UUID, *, limit: int = 50
    ) -> list[Alert]: ...

    async def count_open(self) -> dict[str, int]: ...


def _now() -> datetime:
    return datetime.now(UTC)


class InMemoryAlertRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, Alert] = {}
        self._insertion: list[UUID] = []
        self._lock = asyncio.Lock()

    def _open_by_key(self, alert_key: str) -> Alert | None:
        for alert in self._rows.values():
            if alert.alert_key == alert_key and alert.status == "open":
                return alert
        return None

    async def upsert_open(
        self,
        *,
        alert_key: str,
        code: AlertCode,
        severity: AlertSeverity,
        tenant_id: UUID | None,
        summary: str,
        facts: dict[str, Any],
    ) -> tuple[Alert, bool, bool]:
        async with self._lock:
            now = _now()
            existing = self._open_by_key(alert_key)
            if existing is None:
                alert = Alert(
                    alert_id=uuid4(),
                    alert_key=alert_key,
                    code=code,
                    severity=severity,
                    tenant_id=tenant_id,
                    summary=summary,
                    facts=dict(facts),
                    status="open",
                    occurrences=1,
                    first_seen_at=now,
                    last_seen_at=now,
                )
                self._rows[alert.alert_id] = alert
                self._insertion.append(alert.alert_id)
                return alert, True, False
            escalated = SEVERITY_RANK[severity] > SEVERITY_RANK[existing.severity]
            updated = Alert(
                **{
                    **existing.__dict__,
                    "severity": severity if escalated else existing.severity,
                    "summary": summary,
                    "facts": dict(facts),
                    "occurrences": existing.occurrences + 1,
                    "last_seen_at": now,
                }
            )
            self._rows[existing.alert_id] = updated
            return updated, False, escalated

    async def _resolve(self, alert: Alert | None) -> Alert | None:
        if alert is None or alert.status != "open":
            return None
        resolved = Alert(
            **{**alert.__dict__, "status": "resolved", "resolved_at": _now()}
        )
        self._rows[alert.alert_id] = resolved
        return resolved

    async def resolve(self, alert_key: str, *, resolved_by: str) -> Alert | None:
        async with self._lock:
            return await self._resolve(self._open_by_key(alert_key))

    async def resolve_by_id(self, alert_id: UUID, *, resolved_by: str) -> Alert | None:
        async with self._lock:
            return await self._resolve(self._rows.get(alert_id))

    async def set_delivery(self, alert_id: UUID, status: str) -> None:
        async with self._lock:
            alert = self._rows.get(alert_id)
            if alert is not None:
                self._rows[alert_id] = Alert(
                    **{**alert.__dict__, "delivery_status": status}
                )

    def _ordered(self) -> list[Alert]:
        order = {aid: i for i, aid in enumerate(self._insertion)}
        return sorted(
            self._rows.values(),
            key=lambda a: (a.last_seen_at, order[a.alert_id]),
            reverse=True,
        )

    async def list_alerts(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Alert]:
        rows = [a for a in self._ordered() if status is None or a.status == status]
        return rows[: max(1, min(limit, MAX_LIST_LIMIT))]

    async def list_tenant_alerts(
        self, tenant_id: UUID, *, limit: int = 50
    ) -> list[Alert]:
        rows = [a for a in self._ordered() if a.tenant_id == tenant_id]
        return rows[: max(1, min(limit, MAX_LIST_LIMIT))]

    async def count_open(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for alert in self._rows.values():
            if alert.status == "open":
                counts[alert.severity.value] = counts.get(alert.severity.value, 0) + 1
        return counts


_COLUMNS = (
    "alert_id, alert_key, code, severity, tenant_id, summary, facts, status, "
    "occurrences, first_seen_at, last_seen_at, resolved_at, delivery_status"
)


def _row_to_alert(row: Sequence[Any]) -> Alert:
    facts = row[6]
    if isinstance(facts, str):
        facts = json.loads(facts)
    return Alert(
        alert_id=row[0],
        alert_key=row[1],
        code=AlertCode(row[2]),
        severity=AlertSeverity(row[3]),
        tenant_id=row[4],
        summary=row[5],
        facts=dict(facts or {}),
        status=row[7],
        occurrences=int(row[8]),
        first_seen_at=row[9],
        last_seen_at=row[10],
        resolved_at=row[11],
        delivery_status=row[12],
    )


class PostgresAlertRepository:
    """Platform-transaction writes; tenant reads go through RLS."""

    def __init__(self, database: Any) -> None:
        self.database = database

    async def upsert_open(
        self,
        *,
        alert_key: str,
        code: AlertCode,
        severity: AlertSeverity,
        tenant_id: UUID | None,
        summary: str,
        facts: dict[str, Any],
    ) -> tuple[Alert, bool, bool]:
        async with self.database.platform_transaction() as conn:
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 34))", (alert_key,)
            )
            cursor = await conn.execute(
                f"SELECT {_COLUMNS} FROM operational_alerts "
                "WHERE alert_key = %s AND status = 'open' FOR UPDATE",
                (alert_key,),
            )
            existing_row = await cursor.fetchone()
            if existing_row is None:
                cursor = await conn.execute(
                    "INSERT INTO operational_alerts "
                    "(alert_key, code, severity, tenant_id, summary, facts) "
                    "VALUES (%s, %s, %s, %s, %s, %s::jsonb) "
                    f"RETURNING {_COLUMNS}",
                    (
                        alert_key,
                        code.value,
                        severity.value,
                        tenant_id,
                        summary,
                        json.dumps(facts),
                    ),
                )
                return _row_to_alert(await cursor.fetchone()), True, False
            existing = _row_to_alert(existing_row)
            escalated = SEVERITY_RANK[severity] > SEVERITY_RANK[existing.severity]
            cursor = await conn.execute(
                "UPDATE operational_alerts SET occurrences = occurrences + 1, "
                "last_seen_at = NOW(), summary = %s, facts = %s::jsonb, severity = %s "
                f"WHERE alert_id = %s RETURNING {_COLUMNS}",
                (
                    summary,
                    json.dumps(facts),
                    (severity if escalated else existing.severity).value,
                    existing.alert_id,
                ),
            )
            return _row_to_alert(await cursor.fetchone()), False, escalated

    async def _resolve_where(
        self, clause: str, value: Any, resolved_by: str
    ) -> Alert | None:
        async with self.database.platform_transaction() as conn:
            cursor = await conn.execute(
                "UPDATE operational_alerts SET status = 'resolved', "
                "resolved_at = NOW(), "
                f"resolved_by = %s WHERE {clause} AND status = 'open' "
                f"RETURNING {_COLUMNS}",
                (resolved_by[:120], value),
            )
            row = await cursor.fetchone()
            return _row_to_alert(row) if row else None

    async def resolve(self, alert_key: str, *, resolved_by: str) -> Alert | None:
        return await self._resolve_where("alert_key = %s", alert_key, resolved_by)

    async def resolve_by_id(self, alert_id: UUID, *, resolved_by: str) -> Alert | None:
        return await self._resolve_where("alert_id = %s", alert_id, resolved_by)

    async def set_delivery(self, alert_id: UUID, status: str) -> None:
        async with self.database.platform_transaction() as conn:
            await conn.execute(
                "UPDATE operational_alerts SET delivery_status = %s, "
                "delivery_attempted_at = NOW() WHERE alert_id = %s",
                (status, alert_id),
            )

    async def list_alerts(
        self, *, status: str | None = None, limit: int = 50
    ) -> list[Alert]:
        bounded = max(1, min(limit, MAX_LIST_LIMIT))
        async with self.database.platform_transaction() as conn:
            if status is None:
                cursor = await conn.execute(
                    f"SELECT {_COLUMNS} FROM operational_alerts "
                    "ORDER BY last_seen_at DESC, alert_id LIMIT %s",
                    (bounded,),
                )
            else:
                cursor = await conn.execute(
                    f"SELECT {_COLUMNS} FROM operational_alerts WHERE status = %s "
                    "ORDER BY last_seen_at DESC, alert_id LIMIT %s",
                    (status, bounded),
                )
            return [_row_to_alert(r) for r in await cursor.fetchall()]

    async def list_tenant_alerts(
        self, tenant_id: UUID, *, limit: int = 50
    ) -> list[Alert]:
        bounded = max(1, min(limit, MAX_LIST_LIMIT))
        async with self.database.tenant_transaction(str(tenant_id)) as conn:
            cursor = await conn.execute(
                f"SELECT {_COLUMNS} FROM operational_alerts WHERE tenant_id = %s "
                "ORDER BY last_seen_at DESC, alert_id LIMIT %s",
                (tenant_id, bounded),
            )
            return [_row_to_alert(r) for r in await cursor.fetchall()]

    async def count_open(self) -> dict[str, int]:
        async with self.database.platform_transaction() as conn:
            cursor = await conn.execute(
                "SELECT severity, count(*) FROM operational_alerts "
                "WHERE status = 'open' GROUP BY severity"
            )
            return {str(r[0]): int(r[1]) for r in await cursor.fetchall()}
