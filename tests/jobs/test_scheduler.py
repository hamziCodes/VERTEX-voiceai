"""Phase 14: the jobs runner schedules real work and reports outcomes honestly."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from core.alerts.models import AlertCode
from core.alerts.repository import InMemoryAlertRepository
from core.alerts.service import AlertService
from core.observability.metrics import ucve_jobs_total
from worker_jobs.catalog import build_job_specs
from worker_jobs.scheduler import (
    InMemorySlotClaims,
    JobSpec,
    JobsRunner,
    drain,
    slot_start_for,
)


def _runner(
    specs: list[JobSpec], *, claims=None, alerts=None, clock=None
) -> JobsRunner:
    return JobsRunner(
        specs,
        runner_id="runner-a",
        claims=claims or InMemorySlotClaims(),
        alerts=alerts,
        clock=clock or (lambda: 1_000_000.0),
    )


@pytest.mark.asyncio
async def test_outcomes_distinguish_work_idle_and_disabled() -> None:
    queue = [1, 2, 3]

    async def run_once() -> bool:
        if not queue:
            return False
        queue.pop()
        return True

    async def work() -> int:
        return await drain(run_once, 10)

    runner = _runner(
        [
            JobSpec("drainer", 1.0, work),
            JobSpec("no_backend", 1.0, None, disabled_reason="not configured"),
        ]
    )
    before = ucve_jobs_total.labels(job="drainer", outcome="succeeded").value
    assert await runner.run_tick("drainer") == "succeeded"
    assert runner.status["drainer"].last_items == 3
    assert await runner.run_tick("drainer") == "idle"
    assert await runner.run_tick("no_backend") == "disabled"
    assert (
        ucve_jobs_total.labels(job="drainer", outcome="succeeded").value == before + 1
    )
    snapshot = {s["name"]: s for s in runner.snapshot()}
    assert snapshot["no_backend"]["enabled"] is False
    assert snapshot["no_backend"]["disabled_reason"] == "not configured"


@pytest.mark.asyncio
async def test_singleton_slot_runs_once_across_replicas() -> None:
    claims = InMemorySlotClaims(clock=lambda: 1_000.0)
    calls: list[str] = []

    def make(runner_id: str) -> JobsRunner:
        async def job() -> int:
            calls.append(runner_id)
            return 1

        return JobsRunner(
            [JobSpec("retention_enqueue", 900.0, job, singleton=True)],
            runner_id=runner_id,
            claims=claims,
            clock=lambda: 1_000_000.0,
        )

    results = await asyncio.gather(
        *(make(f"replica-{i}").run_tick("retention_enqueue") for i in range(5))
    )
    assert sorted(results) == ["skipped"] * 4 + ["succeeded"]
    assert len(calls) == 1
    row = claims.rows[("retention_enqueue", slot_start_for(1_000_000.0, 900.0))]
    assert row["status"] == "succeeded" and row["items"] == 1


@pytest.mark.asyncio
async def test_expired_running_claim_is_taken_over() -> None:
    now = [1_000.0]
    claims = InMemorySlotClaims(clock=lambda: now[0])
    slot = datetime(2026, 11, 15, tzinfo=UTC)
    assert await claims.claim("queue_observer", slot, "crashed", lease_s=60)
    assert not await claims.claim("queue_observer", slot, "other", lease_s=60)
    now[0] += 61
    assert await claims.claim("queue_observer", slot, "other", lease_s=60)
    assert claims.rows[("queue_observer", slot)]["attempts"] == 2


@pytest.mark.asyncio
async def test_repeated_failures_raise_alert_and_recovery_resolves_it() -> None:
    alerts = AlertService(InMemoryAlertRepository())
    fail = [True]

    async def flaky() -> int:
        if fail[0]:
            raise ConnectionError("db unavailable")
        return 0

    runner = _runner([JobSpec("privacy_deletion", 1.0, flaky)], alerts=alerts)
    for _ in range(3):
        assert await runner.run_tick("privacy_deletion") == "error"
    open_alerts = await alerts.repository.list_alerts(status="open")
    assert [a.code for a in open_alerts] == [AlertCode.JOB_RUN_FAILED]
    assert open_alerts[0].facts["error"] == "ConnectionError"
    fail[0] = False
    assert await runner.run_tick("privacy_deletion") == "idle"
    assert await alerts.repository.list_alerts(status="open") == []
    assert runner.status["privacy_deletion"].consecutive_failures == 0


@pytest.mark.asyncio
async def test_stop_lets_in_flight_work_finish() -> None:
    started = asyncio.Event()
    finished: list[bool] = []

    async def slow() -> int:
        started.set()
        await asyncio.sleep(0.05)
        finished.append(True)
        return 1

    runner = _runner([JobSpec("slow", 60.0, slow, singleton=False)])
    runner.start()
    await started.wait()
    await runner.stop(timeout_s=2.0)
    assert finished == [True]
    assert not runner.running


def test_without_database_every_job_is_disabled_not_faked() -> None:
    specs = build_job_specs(None, runner_id="r")
    assert {s.name for s in specs} == {
        "post_call_intelligence",
        "webhook_delivery",
        "knowledge_embedding",
        "privacy_deletion",
        "retention_enqueue",
        "queue_observer",
    }
    assert all(not s.enabled and s.disabled_reason for s in specs)


def test_catalogue_never_schedules_known_no_op_jobs() -> None:
    class FakeDatabase:
        pass

    specs = build_job_specs(FakeDatabase(), runner_id="r")
    names = {s.name for s in specs}
    assert not names & {
        "quota_monthly_reset",
        "quota_stale_sweeper",
        "dlq_retry_sweeper",
    }
    by_name = {s.name: s for s in specs}
    # Without injected providers the job is disabled and says how to enable it.
    reason = by_name["post_call_intelligence"].disabled_reason or ""
    assert "PLATFORM_GROQ_API_KEY" in reason
    assert by_name["retention_enqueue"].singleton
    assert by_name["queue_observer"].singleton


def test_legacy_no_op_entrypoints_refuse_to_report_success() -> None:
    import runpy

    for module in (
        "worker_jobs.quota_monthly_reset",
        "worker_jobs.quota_stale_sweeper",
    ):
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_module(module, run_name="__main__")
        assert "not a job" in str(exit_info.value)


def test_jobs_service_exposes_health_metrics_and_protected_schedule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("UCVE_METRICS_BEARER", "jobs-bearer")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from worker_jobs.main import app

    with TestClient(app) as client:
        assert client.get("/health/live").json()["service"] == "worker-jobs"
        ready = client.get("/health/ready").json()
        assert {c["name"] for c in ready["checks"]} == {"database", "scheduler"}
        assert client.get("/jobs").status_code == 401
        jobs = client.get(
            "/jobs", headers={"Authorization": "Bearer jobs-bearer"}
        ).json()
        assert {j["name"] for j in jobs["jobs"]} >= {
            "privacy_deletion",
            "queue_observer",
        }
        assert all(j["last_outcome"] == "disabled" for j in jobs["jobs"])
