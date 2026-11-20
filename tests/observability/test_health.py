"""Phase 14: liveness is separate from readiness; readiness checks real dependencies."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.runtime.health import (
    CheckResult,
    ReadinessProbe,
    install_health_routes,
    profile_check,
    provider_configuration_check,
)


def _app(probe: ReadinessProbe) -> FastAPI:
    app = FastAPI()
    install_health_routes(app, probe)
    return app


def test_liveness_never_depends_on_dependencies() -> None:
    probe = ReadinessProbe("svc")

    async def broken() -> CheckResult:
        return CheckResult.fail("database", "connection refused")

    probe.add_check("database", broken)
    with TestClient(_app(probe)) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        legacy = client.get("/health")
    assert live.status_code == 200 and live.json()["status"] == "alive"
    assert legacy.status_code == 200
    assert ready.status_code == 503
    body = ready.json()
    assert body["status"] == "not_ready"
    assert body["checks"][0] == {
        "name": "database",
        "status": "fail",
        "required": True,
        "detail": "connection refused",
        "latency_ms": body["checks"][0]["latency_ms"],
    }


def test_optional_check_failure_degrades_but_stays_ready() -> None:
    probe = ReadinessProbe("svc")

    async def ok() -> CheckResult:
        return CheckResult.ok("database")

    async def optional_fail() -> CheckResult:
        return CheckResult.fail("telemetry", "collector unreachable")

    probe.add_check("database", ok)
    probe.add_check("telemetry", optional_fail, required=False)
    with TestClient(_app(probe)) as client:
        ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "degraded"


def test_slow_check_times_out_and_fails() -> None:
    probe = ReadinessProbe("svc", check_timeout_s=0.05)

    async def hang() -> CheckResult:
        await asyncio.sleep(5)
        return CheckResult.ok("redis")

    probe.add_check("redis", hang)
    with TestClient(_app(probe)) as client:
        ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["checks"][0]["detail"] == "timed out"


def test_raised_exception_is_reported_by_type_only() -> None:
    probe = ReadinessProbe("svc")

    async def explode() -> CheckResult:
        raise ConnectionError("password=hunter2 host=db.internal")

    probe.add_check("database", explode)
    with TestClient(_app(probe)) as client:
        body = client.get("/health/ready").json()
    assert body["checks"][0]["detail"] == "ConnectionError"
    assert "hunter2" not in str(body)


def test_draining_flips_readiness_but_not_liveness() -> None:
    probe = ReadinessProbe("svc")
    probe.start_draining()
    with TestClient(_app(probe)) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["status"] == "draining"


def test_unknown_runtime_profile_fails_instead_of_silently_using_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UCVE_RUNTIME_PROFILE", "does-not-exist")
    result = asyncio.run(profile_check())
    assert result.status == "fail"
    monkeypatch.setenv("UCVE_RUNTIME_PROFILE", "standard")
    assert asyncio.run(profile_check()).status == "ok"


def test_provider_check_never_makes_network_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("readiness must not call providers")

    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)
    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "1")
    result = asyncio.run(provider_configuration_check())
    assert result.status == "ok"
    assert "mock" in result.detail


@pytest.mark.parametrize(
    ("module", "service"),
    [
        ("control_plane.app", "control-plane"),
        ("worker_raw.main", "worker-raw"),
        ("telephony_gateway.main", "telephony-gateway"),
    ],
)
def test_services_expose_live_and_ready(
    module: str, service: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = __import__(module, fromlist=["app"]).app
    with TestClient(app) as client:
        assert client.get("/health/live").json()["service"] == service
        ready = client.get("/health/ready")
    assert ready.status_code in (200, 503)
    names = {check["name"] for check in ready.json()["checks"]}
    assert "runtime_profile" in names


def test_managed_worker_is_honestly_not_ready() -> None:
    from worker_managed.main import app

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        ready = client.get("/health/ready")
    assert ready.status_code == 503
    assert ready.json()["checks"][0]["name"] == "managed_runtime"


def test_worker_reports_not_ready_at_session_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("UCVE_RUNTIME_PROFILE", "dev")
    import worker_raw.main as worker

    with TestClient(worker.app) as client:
        worker.LOCAL_SESSIONS.count = 5  # dev profile allows 5 per worker
        try:
            ready = client.get("/health/ready").json()
        finally:
            worker.LOCAL_SESSIONS.count = 0
    capacity = next(c for c in ready["checks"] if c["name"] == "session_capacity")
    assert capacity["status"] == "fail"
