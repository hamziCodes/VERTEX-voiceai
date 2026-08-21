"""UCVE Sovereign Worker Node Entrypoint — HTTP health + WebSocket audio."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from control_plane.auth.jwt import verify_session_jwt
from control_plane.routes.session import get_default_mint_context
from core.runtime.env import require_production_secrets
from core.transport.native_websocket import NativeWebSocketTransport
from core.types.events import ControlEvent, ControlEventType
from worker_raw.orchestration.session_config import PipelineSessionConfig

PING_INTERVAL_SEC = 20.0


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    require_production_secrets()
    yield


app = FastAPI(title="UCVE Worker Raw", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "worker-raw"}


async def _load_session_config(token_payload: dict[str, Any]) -> PipelineSessionConfig:
    """Load PipelineSessionConfig from mint context / DB (H3 replaces with Postgres)."""
    session_id = str(token_payload["sub"])
    tenant_id = str(token_payload["tenant_id"])
    agent_id = str(token_payload["agent_id"])
    ctx = get_default_mint_context()
    session = await ctx.session_repo.get_session(tenant_id, session_id)
    compliance_tier = "standard"
    hipaa_baa = False
    if session is not None:
        compliance_tier = session.compliance_tier
    tenant = await ctx.tenant_repo.get_tenant(tenant_id)
    profile = getattr(ctx.tenant_repo, "_compliance_profiles", {}).get(tenant_id)
    if profile is not None:
        compliance_tier = getattr(profile, "compliance_tier", compliance_tier)
        hipaa_baa = getattr(profile, "hipaa_baa_acknowledged_at", None) is not None
    _ = tenant
    return PipelineSessionConfig(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        compliance_tier=compliance_tier,
        hipaa_baa_acknowledged=hipaa_baa,
    )


@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return

    transport = NativeWebSocketTransport()
    ok = await transport.connect("ws", token)
    if not ok:
        await websocket.close(code=4401, reason="invalid token")
        return

    await websocket.accept()
    transport.bind(websocket)

    try:
        payload = verify_session_jwt(token)
        config = await _load_session_config(payload)
    except Exception as exc:
        await websocket.close(code=4401, reason=f"invalid token: {exc}")
        return

    await transport.send_control_event(
        ControlEventType.METRIC,
        {"kind": "session_ready", "session_id": config.session_id},
    )

    stop = asyncio.Event()

    async def _ping_loop() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=PING_INTERVAL_SEC)
                break
            except TimeoutError:
                if not transport.is_connected:
                    break
                await transport.send_control_event("ping", {"interval_sec": PING_INTERVAL_SEC})

    ping_task = asyncio.create_task(_ping_loop())
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                # Echo PCM for H2 connectivity; H5 wires PipelineOrchestrator.
                await transport.send_audio_frame(message["bytes"])
                continue
            text = message.get("text")
            if not text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            event_type = data.get("event_type") or data.get("type")
            if event_type in ("pong", "control.pong"):
                continue
            if event_type in ("ping", "control.ping"):
                await transport.send_control_event(
                    ControlEventType.PONG, {"t": time.time()}
                )
                continue
            if event_type == "barge_in":
                await transport.send_control_event(
                    ControlEventType.BARGE_IN, data.get("payload") or {}
                )
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass
        await transport.close()


def main() -> None:
    """Bind HTTP/WS on 8081 (compose / Dockerfile contract)."""
    uvicorn.run(
        "worker_raw.main:app",
        host="0.0.0.0",
        port=8081,
        log_level="info",
    )


if __name__ == "__main__":
    main()
