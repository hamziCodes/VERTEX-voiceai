"""Background job scheduler with durable singleton claims (Phase 14).

Two kinds of work:

- **Queue drainers** process rows that already carry their own durable lease
  (``FOR UPDATE SKIP LOCKED`` plus lease expiry and dead-lettering in the
  repositories). Any number of runner replicas can drain the same queue.
- **Singleton periodic jobs** must run once per time slot across replicas. A
  runner claims ``(job_name, slot_start)`` in ``scheduled_job_runs``; only one
  replica wins, and a crashed runner's expired lease can be taken over.

Every execution is counted in ``ucve_jobs_total`` with an honest outcome:
``succeeded`` (did work), ``idle`` (nothing to do), ``skipped`` (another
replica owns the slot), ``error``. A job with no configured backend is
``disabled`` with a reason and is never reported as succeeding. Three
consecutive errors raise a ``JOB_RUN_FAILED`` alert, resolved on recovery.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.alerts.models import AlertCode, AlertSeverity
from core.observability.metrics import ucve_jobs_total

logger = logging.getLogger(__name__)

FAILURE_ALERT_THRESHOLD = 3


class SlotClaims(Protocol):
    async def claim(
        self, job_name: str, slot_start: datetime, runner_id: str, lease_s: float
    ) -> bool: ...

    async def finish(
        self,
        job_name: str,
        slot_start: datetime,
        runner_id: str,
        *,
        status: str,
        items: int,
        error_code: str | None,
    ) -> None: ...


class InMemorySlotClaims:
    """Process-local claims for development and tests."""

    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.rows: dict[tuple[str, datetime], dict[str, Any]] = {}
        self._clock = clock
        self._lock = asyncio.Lock()

    async def claim(
        self, job_name: str, slot_start: datetime, runner_id: str, lease_s: float
    ) -> bool:
        async with self._lock:
            now = self._clock()
            row = self.rows.get((job_name, slot_start))
            if row is not None and not (
                row["status"] == "running" and row["lease_expires_at"] < now
            ):
                return False
            attempts = 1 if row is None else row["attempts"] + 1
            self.rows[(job_name, slot_start)] = {
                "runner_id": runner_id,
                "status": "running",
                "lease_expires_at": now + lease_s,
                "attempts": attempts,
                "items": 0,
                "error_code": None,
            }
            return True

    async def finish(
        self,
        job_name: str,
        slot_start: datetime,
        runner_id: str,
        *,
        status: str,
        items: int,
        error_code: str | None,
    ) -> None:
        async with self._lock:
            row = self.rows.get((job_name, slot_start))
            if row is not None and row["runner_id"] == runner_id:
                row.update(status=status, items=items, error_code=error_code)


class PostgresSlotClaims:
    def __init__(self, database: Any) -> None:
        self.database = database

    async def claim(
        self, job_name: str, slot_start: datetime, runner_id: str, lease_s: float
    ) -> bool:
        async with self.database.platform_transaction() as conn:
            cursor = await conn.execute(
                "INSERT INTO scheduled_job_runs "
                "(job_name, slot_start, runner_id, lease_expires_at) "
                "VALUES (%s, %s, %s, NOW() + make_interval(secs => %s)) "
                "ON CONFLICT (job_name, slot_start) DO UPDATE SET "
                "runner_id = EXCLUDED.runner_id, claimed_at = NOW(), "
                "lease_expires_at = EXCLUDED.lease_expires_at, "
                "attempts = scheduled_job_runs.attempts + 1 "
                "WHERE scheduled_job_runs.status = 'running' "
                "AND scheduled_job_runs.lease_expires_at < NOW() "
                "RETURNING runner_id",
                (job_name, slot_start, runner_id, float(lease_s)),
            )
            return await cursor.fetchone() is not None

    async def finish(
        self,
        job_name: str,
        slot_start: datetime,
        runner_id: str,
        *,
        status: str,
        items: int,
        error_code: str | None,
    ) -> None:
        async with self.database.platform_transaction() as conn:
            await conn.execute(
                "UPDATE scheduled_job_runs SET status = %s, finished_at = NOW(), "
                "items_processed = %s, error_code = %s "
                "WHERE job_name = %s AND slot_start = %s AND runner_id = %s",
                (status, items, error_code, job_name, slot_start, runner_id),
            )


@dataclass
class JobSpec:
    """A scheduled unit of work.

    ``run`` returns the number of items processed. ``disabled_reason`` marks a
    job whose backend is not configured; it is reported, never executed.
    """

    name: str
    interval_s: float
    run: Callable[[], Awaitable[int]] | None
    singleton: bool = False
    disabled_reason: str | None = None
    lease_s: float | None = None

    @property
    def enabled(self) -> bool:
        return self.disabled_reason is None and self.run is not None


@dataclass
class JobStatus:
    name: str
    enabled: bool
    disabled_reason: str | None
    interval_s: float
    last_started_at: float | None = None
    last_outcome: str | None = None
    last_items: int = 0
    last_error_code: str | None = None
    consecutive_failures: int = 0
    runs: dict[str, int] = field(default_factory=dict)

    def to_public(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "disabled_reason": self.disabled_reason,
            "interval_s": self.interval_s,
            "last_started_at": (
                datetime.fromtimestamp(self.last_started_at, UTC).isoformat()
                if self.last_started_at
                else None
            ),
            "last_outcome": self.last_outcome,
            "last_items": self.last_items,
            "last_error_code": self.last_error_code,
            "consecutive_failures": self.consecutive_failures,
            "runs": dict(self.runs),
        }


def slot_start_for(now: float, interval_s: float) -> datetime:
    return datetime.fromtimestamp(math.floor(now / interval_s) * interval_s, UTC)


async def drain(run_once: Callable[[], Awaitable[bool]], limit: int) -> int:
    """Call ``run_once`` until it reports no work or ``limit`` is reached."""
    processed = 0
    while processed < limit and await run_once():
        processed += 1
    return processed


class JobsRunner:
    def __init__(
        self,
        specs: list[JobSpec],
        *,
        runner_id: str,
        claims: SlotClaims,
        alerts: Any | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        names = [s.name for s in specs]
        if len(names) != len(set(names)):
            raise ValueError("Job names must be unique.")
        self.specs = {s.name: s for s in specs}
        self.runner_id = runner_id
        self.claims = claims
        self.alerts = alerts
        self.clock = clock
        self.status = {
            s.name: JobStatus(s.name, s.enabled, s.disabled_reason, s.interval_s)
            for s in specs
        }
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._in_flight = 0

    def _record(self, name: str, outcome: str, items: int, error: str | None) -> None:
        status = self.status[name]
        status.last_outcome = outcome
        status.last_items = items
        status.last_error_code = error
        status.runs[outcome] = status.runs.get(outcome, 0) + 1
        ucve_jobs_total.labels(job=name, outcome=outcome).inc()

    async def run_tick(self, name: str) -> str:
        spec = self.specs[name]
        status = self.status[name]
        if not spec.enabled or spec.run is None:
            self._record(name, "disabled", 0, None)
            return "disabled"
        now = self.clock()
        status.last_started_at = now
        slot = slot_start_for(now, spec.interval_s) if spec.singleton else None
        if slot is not None:
            lease = spec.lease_s or max(60.0, spec.interval_s)
            if not await self.claims.claim(name, slot, self.runner_id, lease):
                self._record(name, "skipped", 0, None)
                return "skipped"
        self._in_flight += 1
        try:
            items = await spec.run()
        except Exception as exc:  # noqa: BLE001 - recorded, alerted, loop continues
            error = type(exc).__name__[:64]
            logger.error("job %s failed: %s", name, error)
            self._record(name, "error", 0, error)
            if slot is not None:
                await self.claims.finish(
                    name,
                    slot,
                    self.runner_id,
                    status="failed",
                    items=0,
                    error_code=error,
                )
            status.consecutive_failures += 1
            if status.consecutive_failures >= FAILURE_ALERT_THRESHOLD and self.alerts:
                await self.alerts.raise_safely(
                    alert_key=f"job_run_failed:{name}",
                    code=AlertCode.JOB_RUN_FAILED,
                    severity=AlertSeverity.ERROR,
                    summary=f"Scheduled job {name} failed repeatedly.",
                    facts={
                        "job": name,
                        "consecutive_failures": status.consecutive_failures,
                        "error": error,
                    },
                )
            return "error"
        finally:
            self._in_flight -= 1
        outcome = "succeeded" if items > 0 else "idle"
        self._record(name, outcome, items, None)
        if slot is not None:
            await self.claims.finish(
                name,
                slot,
                self.runner_id,
                status="succeeded",
                items=items,
                error_code=None,
            )
        if status.consecutive_failures and self.alerts:
            await self.alerts.resolve(
                f"job_run_failed:{name}", resolved_by="jobs-runner"
            )
        status.consecutive_failures = 0
        return outcome

    async def _loop(self, name: str) -> None:
        spec = self.specs[name]
        while not self._stop.is_set():
            outcome = await self.run_tick(name)
            # A drainer that filled its batch goes again immediately.
            if outcome == "succeeded" and not spec.singleton:
                await asyncio.sleep(0)
                continue
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=spec.interval_s)

    def start(self) -> None:
        for name, spec in self.specs.items():
            if spec.enabled:
                self._tasks.append(
                    asyncio.get_running_loop().create_task(
                        self._loop(name), name=f"job:{name}"
                    )
                )
            else:
                self._record(name, "disabled", 0, None)

    @property
    def running(self) -> bool:
        return bool(self._tasks) and not all(t.done() for t in self._tasks)

    async def stop(self, *, timeout_s: float = 30.0) -> None:
        """Stop scheduling; let in-flight items finish within ``timeout_s``."""
        self._stop.set()
        if not self._tasks:
            return
        done, pending = await asyncio.wait(self._tasks, timeout=timeout_s)
        for task in pending:
            task.cancel()
        for task in pending:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    def snapshot(self) -> list[dict[str, Any]]:
        return [status.to_public() for status in self.status.values()]
