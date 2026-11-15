"""Phase 14 disposable PostgreSQL proof for migration 034 (operational alerts)."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DB_TESTS") != "1",
    reason="RUN_LIVE_DB_TESTS!=1 - disposable PostgreSQL only",
)


@pytest.fixture(scope="module")
def event_loop_policy() -> asyncio.AbstractEventLoopPolicy:
    if sys.platform == "win32":
        return asyncio.WindowsSelectorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


@pytest.mark.asyncio
async def test_phase14_alerts_dedup_concurrency_and_tenant_rls() -> None:
    import psycopg
    from psycopg import errors

    from core.alerts.models import AlertCode, AlertSeverity
    from core.alerts.repository import PostgresAlertRepository
    from core.alerts.service import AlertService
    from core.db.async_pg import AsyncDatabase
    from infra.db.migrate import apply_migrations_async

    database_url = os.environ["DATABASE_URL"]
    await apply_migrations_async(database_url)
    database = AsyncDatabase(database_url=database_url, min_size=1, max_size=6)
    await database.open()
    fixture = await psycopg.AsyncConnection.connect(database_url, autocommit=True)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        await fixture.execute(
            "INSERT INTO tenants (id, name) VALUES (%s, 'Alerts A'), (%s, 'Alerts B')",
            (tenant_a, tenant_b),
        )
        service = AlertService(PostgresAlertRepository(database))

        async def soft_cap(tenant: uuid.UUID):
            return await service.raise_alert(
                alert_key=f"quota_soft_cap:{tenant}:2026-11",
                code=AlertCode.QUOTA_SOFT_CAP,
                severity=AlertSeverity.WARNING,
                summary="Usage passed the soft warning threshold for this month.",
                tenant_id=tenant,
                facts={"period": "2026-11"},
            )

        # Ten concurrent raisers produce exactly one open row.
        results = await asyncio.gather(*(soft_cap(tenant_a) for _ in range(10)))
        assert sum(1 for r in results if r.is_new) == 1
        await soft_cap(tenant_b)
        rows = await (
            await fixture.execute(
                "SELECT tenant_id, occurrences, delivery_status "
                "FROM operational_alerts "
                "WHERE code = 'QUOTA_SOFT_CAP' ORDER BY occurrences DESC"
            )
        ).fetchall()
        assert rows[0] == (tenant_a, 10, "not_configured")
        assert rows[1][0] == tenant_b

        # A platform alert is invisible to tenants; a tenant sees only itself.
        await service.raise_alert(
            alert_key="capacity:session_admission",
            code=AlertCode.CAPACITY_EXHAUSTED,
            severity=AlertSeverity.ERROR,
            summary="Session admission refused a session: worker capacity reached.",
            facts={"max_sessions": 5},
        )
        async with fixture.transaction():
            await fixture.execute("SET LOCAL ROLE ucve_app")
            await fixture.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_a),)
            )
            visible = await (
                await fixture.execute("SELECT tenant_id, code FROM operational_alerts")
            ).fetchall()
        assert visible == [(tenant_a, "QUOTA_SOFT_CAP")]
        with pytest.raises(errors.InsufficientPrivilege):
            async with fixture.transaction():
                await fixture.execute("SET LOCAL ROLE ucve_app")
                await fixture.execute(
                    "UPDATE operational_alerts SET status = 'resolved', "
                    "resolved_at = NOW()"
                )

        # Resolution closes the row; the next raise opens a fresh one.
        assert await service.resolve("capacity:session_admission", resolved_by="test")
        again = await service.raise_alert(
            alert_key="capacity:session_admission",
            code=AlertCode.CAPACITY_EXHAUSTED,
            severity=AlertSeverity.ERROR,
            summary="Session admission refused a session: worker capacity reached.",
        )
        assert again.is_new
        counts = await service.repository.count_open()
        assert counts == {"warning": 2, "error": 1}

        # Constraint: unknown codes and content-length summaries are refused.
        with pytest.raises(errors.CheckViolation):
            await fixture.execute(
                "INSERT INTO operational_alerts (alert_key, code, severity, summary) "
                "VALUES ('k:x', 'MADE_UP', 'warning', 's')"
            )
    finally:
        await fixture.execute(
            "DELETE FROM tenants WHERE id IN (%s, %s)", (tenant_a, tenant_b)
        )
        await fixture.execute("DELETE FROM operational_alerts")
        await fixture.close()
        await database.close()
