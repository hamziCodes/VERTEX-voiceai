"""UCVE Sovereign Worker Node Entrypoint — HTTP health + WebSocket audio."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from control_plane.auth.jwt import verify_session_jwt
from control_plane.routes.session import get_default_mint_context
from core.db.repos.tenant_repo import TenantRepository
from core.runtime.env import require_production_secrets
from core.transport.native_websocket import NativeWebSocketTransport
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.ws_constants import WS_MAX_SIZE_BYTES
from worker_raw.ws_session import WebSocketSessionRunner


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    require_production_secrets()
    yield


app = FastAPI(title="Wavia Worker Raw", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "worker-raw"}


@app.get("/")
async def root() -> dict[str, str]:
    """Browser / tooling probes hit `/`; return service identity instead of 404."""
    return {"status": "ok", "service": "worker-raw", "ws": "/ws/audio"}


@app.get("/json/version")
async def json_version() -> dict[str, str]:
    """Chrome/CDP-style probes often hit this on open ports — avoid noisy 404s."""
    return {
        "service": "ucve-worker-raw",
        "version": app.version or "0.1.0",
        "note": "Not a Chrome DevTools endpoint",
    }

async def _load_session_config(
    token_payload: dict[str, str],
    *,
    stt_provider: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    tts_provider: str | None = None,
    tts_voice_id: str | None = None,
) -> PipelineSessionConfig:
    """Load PipelineSessionConfig from mint context / DB."""
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
    if isinstance(ctx.tenant_repo, TenantRepository):
        profile = ctx.tenant_repo.get_compliance_profile(tenant_id)
    else:
        profile = getattr(ctx.tenant_repo, "_compliance_profiles", {}).get(tenant_id)
    if profile is not None:
        compliance_tier = getattr(profile, "compliance_tier", compliance_tier)
        hipaa_baa = getattr(profile, "hipaa_baa_acknowledged_at", None) is not None
    _ = tenant
    import os

    greeting = (os.environ.get("UCVE_INITIAL_GREETING") or "").strip() or None
    chosen_llm_model = (llm_model or "").strip()
    if not chosen_llm_model:
        lp = (llm_provider or "").strip().lower()
        if lp == "gemini":
            chosen_llm_model = "gemini-2.5-flash"
        elif lp == "openai":
            chosen_llm_model = "gpt-4o-mini"
        else:
            chosen_llm_model = "openai/gpt-oss-120b"
    return PipelineSessionConfig(
        session_id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        compliance_tier=compliance_tier,
        hipaa_baa_acknowledged=hipaa_baa,
        initial_greeting=greeting,
        stt_provider=stt_provider or "gladia",
        llm_provider=llm_provider or "groq",
        llm_model=chosen_llm_model,
        tts_provider=tts_provider or "uplift",
        tts_voice_id=(tts_voice_id or "default"),
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
        config = await _load_session_config(
            payload,
            stt_provider=websocket.query_params.get("stt_provider"),
            llm_provider=websocket.query_params.get("llm_provider"),
            llm_model=websocket.query_params.get("llm_model"),
            tts_provider=websocket.query_params.get("tts_provider"),
            tts_voice_id=websocket.query_params.get("tts_voice_id"),
        )
    except Exception as exc:
        await websocket.close(code=4401, reason=f"invalid token: {exc}")
        return

    async def _on_audio_out(pcm_bytes: bytes) -> None:
        await transport.send_audio_frame(pcm_bytes)

    async def _on_transcript(speaker: str, text: str) -> None:
        await transport.send_control_event("transcript", {"speaker": speaker, "text": text})

    orchestrator = PipelineOrchestrator(
        on_audio_out=_on_audio_out,
        on_transcript=_on_transcript,
    )
    await orchestrator.apply_provider_selection(config)

    raw_rate = websocket.query_params.get("sample_rate") or websocket.query_params.get("rate")
    client_rate = 16000
    if raw_rate:
        try:
            client_rate = int(raw_rate)
        except ValueError:
            client_rate = 16000

    runner = WebSocketSessionRunner(
        websocket,
        transport,
        orchestrator,
        config,
        client_sample_rate=client_rate,
    )
    try:
        await runner.start()
    except WebSocketDisconnect:
        pass


def main() -> None:
    """Bind HTTP/WS on 8081 (compose / Dockerfile contract)."""
    uvicorn.run(
        "worker_raw.main:app",
        host="0.0.0.0",
        port=8081,
        log_level="info",
        ws_max_size=WS_MAX_SIZE_BYTES,
    )


if __name__ == "__main__":
    main()
