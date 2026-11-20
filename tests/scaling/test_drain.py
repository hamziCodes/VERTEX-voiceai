"""Phase 14: SIGTERM drains live sessions instead of cutting them."""

from __future__ import annotations

import asyncio

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.runtime.drain import DrainingServer
from core.runtime.health import ReadinessProbe, install_health_routes


def _server(active: list[int], timeout_s: float = 5.0, clock=None) -> DrainingServer:
    probe = ReadinessProbe("svc")
    return DrainingServer(
        uvicorn.Config(FastAPI()),
        probe=probe,
        active_sessions=lambda: active[0],
        drain_timeout_s=timeout_s,
        poll_interval_s=0.01,
        **({"clock": clock} if clock else {}),
    )


@pytest.mark.asyncio
async def test_drain_waits_for_last_session_then_stops() -> None:
    active = [2]
    server = _server(active)
    task = asyncio.create_task(server.drain())
    await asyncio.sleep(0.05)
    assert server.probe.draining and not server.should_exit
    active[0] = 1
    await asyncio.sleep(0.05)
    assert not server.should_exit
    active[0] = 0
    assert await task == "drained"
    assert server.should_exit and not server.force_exit


@pytest.mark.asyncio
async def test_drain_gives_up_at_timeout() -> None:
    now = [0.0]
    server = _server([3], timeout_s=10.0, clock=lambda: now[0])
    task = asyncio.create_task(server.drain())
    await asyncio.sleep(0.03)
    assert not server.should_exit
    now[0] = 10.5
    assert await task == "timeout"
    assert server.should_exit


@pytest.mark.asyncio
async def test_first_signal_drains_second_signal_forces_exit() -> None:
    import signal

    active = [1]
    server = _server(active)
    server._loop = asyncio.get_running_loop()
    server.handle_exit(signal.SIGTERM, None)
    assert server.probe.draining
    assert not server.should_exit
    await asyncio.sleep(0.03)
    assert not server.should_exit  # still waiting on the live session
    server.handle_exit(signal.SIGTERM, None)
    assert server.should_exit and server.force_exit


def test_draining_readiness_is_503_while_liveness_stays_up() -> None:
    probe = ReadinessProbe("svc")
    app = FastAPI()
    install_health_routes(app, probe)
    probe.start_draining()
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").json()["status"] == "draining"


def test_draining_worker_refuses_new_sessions_with_1013(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import worker_raw.main as worker

    monkeypatch.setattr(worker.readiness, "_draining", True)
    with TestClient(worker.app) as client:
        with pytest.raises(WebSocketDisconnect) as closed:
            with client.websocket_connect("/ws/audio?token=anything") as ws:
                ws.receive_text()
    assert closed.value.code == 1013


def test_cluster_capacity_scales_with_worker_replicas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.runtime.admission import cluster_session_capacity
    from core.runtime.profile_loader import load_profile

    standard = load_profile("standard")
    monkeypatch.delenv("UCVE_CLUSTER_MAX_SESSIONS", raising=False)
    monkeypatch.setenv("UCVE_WORKER_REPLICAS", "4")
    assert cluster_session_capacity(standard) == 100
    monkeypatch.setenv("UCVE_CLUSTER_MAX_SESSIONS", "70")
    assert cluster_session_capacity(standard) == 70
    monkeypatch.setenv("UCVE_CLUSTER_MAX_SESSIONS", "0")
    with pytest.raises(ValueError):
        cluster_session_capacity(standard)
