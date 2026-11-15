"""Wavia jobs runner process: scheduled and queue-draining background work.

Run with ``python -m worker_jobs.main`` (port 8084). It exposes the same
observability surface as the other services (``/health/live``,
``/health/ready``, ``/metrics``) plus ``/jobs`` for the current schedule state.
Readiness fails without a database in protected environments and when the
scheduler loop has stopped.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Header

from core.alerts.service import build_alert_service, set_process_alert_service
from core.db.async_pg import get_default_database
from core.db.pg import use_memory_repos
from core.observability.http import (
    install_observability,
    observability_runtime,
    render_metrics,
)
from core.runtime.env import is_protected_environment, require_production_secrets
from core.runtime.health import (
    CheckResult,
    ReadinessProbe,
    database_check,
    install_health_routes,
)
from worker_jobs.catalog import build_job_specs, default_runner_id
from worker_jobs.scheduler import InMemorySlotClaims, JobsRunner, PostgresSlotClaims

SERVICE_NAME = "worker-jobs"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    require_production_secrets()
    async with observability_runtime(app, SERVICE_NAME):
        database = None
        if not use_memory_repos():
            database = get_default_database()
            await database.open()
        app.state.database = database
        alerts = build_alert_service(database)
        set_process_alert_service(alerts)
        runner_id = default_runner_id()
        runner = JobsRunner(
            build_job_specs(database, runner_id=runner_id, alerts=alerts),
            runner_id=runner_id,
            claims=PostgresSlotClaims(database) if database else InMemorySlotClaims(),
            alerts=alerts,
        )
        app.state.jobs_runner = runner
        if os.environ.get("WAVIA_JOBS_AUTOSTART", "1") != "0":
            runner.start()
        try:
            yield
        finally:
            readiness.start_draining()
            await runner.stop(
                timeout_s=float(os.environ.get("WAVIA_JOBS_DRAIN_S", "30"))
            )
            set_process_alert_service(None)
            if database is not None:
                await database.close()


app = FastAPI(title="Wavia Jobs Runner", version="0.1.0", lifespan=lifespan)
install_observability(app, SERVICE_NAME)


async def _scheduler_check() -> CheckResult:
    runner: JobsRunner | None = getattr(app.state, "jobs_runner", None)
    if runner is None:
        return CheckResult.fail("scheduler", "not started")
    enabled = [s for s in runner.status.values() if s.enabled]
    if not enabled:
        if is_protected_environment():
            return CheckResult.fail("scheduler", "no jobs enabled")
        return CheckResult.ok("scheduler", "no jobs enabled (development)")
    if not runner.running:
        return CheckResult.fail("scheduler", "scheduler loop stopped")
    return CheckResult.ok("scheduler", f"{len(enabled)} jobs scheduled")


readiness = ReadinessProbe(SERVICE_NAME)
readiness.add_check(
    "database", database_check(lambda: getattr(app.state, "database", None))
)
readiness.add_check("scheduler", _scheduler_check)
install_health_routes(app, readiness)


@app.get("/jobs", include_in_schema=False)
async def jobs(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict[str, Any]:
    """Schedule state for operators; same bearer as ``/metrics``."""
    render_metrics(authorization)  # raises 401/503 exactly like /metrics
    runner: JobsRunner | None = getattr(app.state, "jobs_runner", None)
    return {"service": SERVICE_NAME, "jobs": runner.snapshot() if runner else []}


def main() -> None:
    uvicorn.run(
        "worker_jobs.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8084")),
        log_level="info",
        timeout_graceful_shutdown=int(os.environ.get("WAVIA_JOBS_DRAIN_S", "30")) + 5,
    )


if __name__ == "__main__":
    main()
