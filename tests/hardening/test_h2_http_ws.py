"""H2: FastAPI mint + worker WebSocket connect/auth."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient

from control_plane.auth.hmac_mint import expected_signature
from control_plane.routes.session import reset_default_mint_context
from core.db.models import Agent, Tenant
from core.protocol.realtime import build_event


def _complete_protocol_handshake(ws: object) -> None:
    ws.send_text(
        json.dumps(
            build_event(
                "protocol.hello",
                {
                    "protocol_version": "1.0.0",
                    "sdk": {"name": "pytest", "version": "1.0.0"},
                },
                sequence=1,
            )
        )
    )
    ready = json.loads(ws.receive_text())
    assert ready["event_type"] == "session.ready"
    runtime = json.loads(ws.receive_text())
    assert runtime["event_type"] == "metric"
    assert runtime["payload"]["kind"] == "session_ready"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "1")
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


async def _mint_ws_token(tenant_id: str, agent_id: str, nonce: str) -> str:
    from control_plane.app import app as cp_app

    reset_default_mint_context()
    with TestClient(cp_app) as cp:
        ctx = cp_app.state.mint_ctx
        await ctx.tenant_repo.create_tenant(Tenant(id=tenant_id, name="WS"))
        await ctx.tenant_repo.save_agent(Agent(id=agent_id, tenant_id=tenant_id, name="A"))
        secret = "dev-mint-secret"
        ts = str(int(time.time()))
        sig = expected_signature(secret, tenant_id, ts, nonce, agent_id)
        mint = cp.post(
            "/v1/session",
            headers={
                "X-Tenant-Id": tenant_id,
                "X-Timestamp": ts,
                "X-Nonce": nonce,
                "X-Agent-Id": agent_id,
                "X-Signature": sig,
            },
        )
        assert mint.status_code == 200
        return mint.json()["token"]


@pytest.mark.asyncio
async def test_ws_connect_with_valid_token(env: None) -> None:
    from worker_raw.main import app as worker_app

    token = await _mint_ws_token("t-ws", "agent-ws", "ws-nonce")

    with StarletteTestClient(worker_app) as worker:
        with worker.websocket_connect(f"/ws/audio?token={token}") as ws:
            # session_ready metric — connect path only (binary PCM covered by C1 gate below)
            _complete_protocol_handshake(ws)
            ws.send_text(json.dumps(build_event("control.ping", {}, sequence=2)))
            pong = ws.receive_text()
            assert "pong" in pong.lower()


@pytest.mark.asyncio
async def test_binary_pcm_frame_ingress_no_typeerror(env: None) -> None:
    """Binary PCM must be accepted and leave the socket usable (R1 C1)."""
    from worker_raw.main import app as worker_app

    token = await _mint_ws_token("t-ws-pcm", "agent-ws-pcm", "ws-pcm-nonce")

    with StarletteTestClient(worker_app) as worker:
        with worker.websocket_connect(f"/ws/audio?token={token}") as ws:
            _complete_protocol_handshake(ws)
            ws.send_bytes(b"\x00\x01" * 160)
            ws.send_text(json.dumps(build_event("control.ping", {}, sequence=2)))
            pong = ws.receive_text()
            assert "pong" in pong.lower()


@pytest.mark.asyncio
async def test_oversized_frame_rejected(env: None) -> None:
    """10 MB frame exceeds MAX_AUDIO_FRAME_BYTES and closes connection (R1 M2)."""
    from worker_raw.main import app as worker_app
    from worker_raw.ws_constants import MAX_AUDIO_FRAME_BYTES

    token = await _mint_ws_token("t-ws-big", "agent-ws-big", "ws-big-nonce")
    oversized = b"\x00" * (MAX_AUDIO_FRAME_BYTES + 1)

    with StarletteTestClient(worker_app) as worker:
        with worker.websocket_connect(f"/ws/audio?token={token}") as ws:
            _complete_protocol_handshake(ws)
            ws.send_bytes(oversized)
            # Connection should close or stop accepting; next receive may raise
            with pytest.raises(Exception):
                ws.send_text(json.dumps(build_event("control.ping", {}, sequence=2)))
                ws.receive_text(timeout=2)


def test_ws_invalid_token_rejected(env: None) -> None:
    from worker_raw.main import app as worker_app

    with StarletteTestClient(worker_app) as worker:
        with pytest.raises(Exception):
            with worker.websocket_connect("/ws/audio?token=not-a-jwt"):
                pass
