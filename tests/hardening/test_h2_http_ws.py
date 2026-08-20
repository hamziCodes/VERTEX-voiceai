"""H2: FastAPI mint + worker WebSocket connect/auth."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from control_plane.auth.hmac_mint import expected_signature
from control_plane.routes.session import reset_default_mint_context
from core.db.models import Agent, Tenant


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "dev-mint-secret")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "test-metrics-bearer-32chars-ok")
    monkeypatch.setenv("UCVE_WS_PUBLIC_URL", "ws://localhost:8081/ws/audio")
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_default_mint_context()


@pytest.fixture
def cp_client(env: None) -> TestClient:
    from control_plane.app import app

    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_seed_and_mint_returns_jwt(cp_client: TestClient) -> None:
    from control_plane.app import app

    ctx = app.state.mint_ctx
    await ctx.tenant_repo.create_tenant(Tenant(id="t-h2", name="H2"))
    await ctx.tenant_repo.save_agent(Agent(id="agent-h2", tenant_id="t-h2", name="A"))

    secret = "dev-mint-secret"
    ts = str(int(time.time()))
    nonce = "h2-nonce-1"
    sig = expected_signature(secret, "t-h2", ts, nonce, "agent-h2")
    resp = cp_client.post(
        "/v1/session",
        headers={
            "X-Tenant-Id": "t-h2",
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Agent-Id": "agent-h2",
            "X-Signature": sig,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert body["ws_url"].endswith("/ws/audio")
    assert "session_id" in body


def test_health_endpoints(env: None) -> None:
    from control_plane.app import app as cp_app
    from worker_raw.main import app as worker_app

    with TestClient(cp_app) as c1:
        assert c1.get("/health").json()["service"] == "control-plane"
    with TestClient(worker_app) as c2:
        assert c2.get("/health").json()["service"] == "worker-raw"


def test_metrics_requires_bearer(cp_client: TestClient) -> None:
    assert cp_client.get("/metrics").status_code == 401
    ok = cp_client.get(
        "/metrics", headers={"Authorization": "Bearer test-metrics-bearer-32chars-ok"}
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_ws_connect_with_valid_token(env: None) -> None:
    from control_plane.app import app as cp_app
    from worker_raw.main import app as worker_app

    reset_default_mint_context()
    with TestClient(cp_app) as cp:
        ctx = cp_app.state.mint_ctx
        await ctx.tenant_repo.create_tenant(Tenant(id="t-ws", name="WS"))
        await ctx.tenant_repo.save_agent(Agent(id="agent-ws", tenant_id="t-ws", name="A"))
        secret = "dev-mint-secret"
        ts = str(int(time.time()))
        nonce = "ws-nonce"
        sig = expected_signature(secret, "t-ws", ts, nonce, "agent-ws")
        mint = cp.post(
            "/v1/session",
            headers={
                "X-Tenant-Id": "t-ws",
                "X-Timestamp": ts,
                "X-Nonce": nonce,
                "X-Agent-Id": "agent-ws",
                "X-Signature": sig,
            },
        )
        assert mint.status_code == 200
        token = mint.json()["token"]

    with StarletteTestClient(worker_app) as worker:
        with worker.websocket_connect(f"/ws/audio?token={token}") as ws:
            # session_ready metric
            msg = ws.receive_text()
            assert "session_ready" in msg or "metric" in msg
            ws.send_bytes(b"\x00\x01" * 160)
            echoed = ws.receive_bytes()
            assert echoed == b"\x00\x01" * 160


def test_ws_invalid_token_rejected(env: None) -> None:
    from worker_raw.main import app as worker_app

    with StarletteTestClient(worker_app) as worker:
        with pytest.raises(Exception):
            with worker.websocket_connect("/ws/audio?token=not-a-jwt"):
                pass
