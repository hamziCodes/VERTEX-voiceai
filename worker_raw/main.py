"""UCVE Sovereign Worker Node Entrypoint — HTTP health + WebSocket audio."""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from control_plane.auth.jwt import verify_session_jwt
from control_plane.routes.session import (
    MintContext,
    get_default_mint_context,
    unsafe_session_overrides_enabled,
)
from core.db.async_pg import get_default_database
from core.db.pg import use_memory_repos
from core.providers.mode import provider_runtime_status
from core.redis.nonce_store import ReplayStoreUnavailableError
from core.redis.token_store import SessionTokenStore
from core.runtime.admission import (
    AdmissionStoreUnavailableError,
    CapacityExceededError,
    SessionAdmissionController,
)
from core.runtime.env import require_production_secrets
from core.runtime.session_plan import RuntimeSessionPlan, SessionPlanIntegrityError
from core.transport.native_websocket import NativeWebSocketTransport
from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig
from worker_raw.security.ws_policy import (
    WSSecurityViolation,
    validate_demo_provider_overrides,
)
from worker_raw.ws_constants import WS_MAX_SIZE_BYTES
from worker_raw.ws_session import ProtocolSessionError, WebSocketSessionRunner


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    require_production_secrets()
    database = None
    if not use_memory_repos():
        database = get_default_database()
        await database.open()
    _app.state.database = database
    _app.state.token_store = SessionTokenStore()
    try:
        yield
    finally:
        if database is not None:
            await database.close()


app = FastAPI(title="Wavia Worker Raw", version="0.1.0", lifespan=lifespan)
session_admission = SessionAdmissionController()
_default_token_store = SessionTokenStore()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionPlanLoadError(ValueError):
    """Raised when a worker cannot authenticate a session's pinned plan."""


class ProviderModeConstraintError(ValueError):
    """Raised before provider startup when signed runtime constraints do not match."""


def _enforce_provider_mode_constraint(
    token_payload: dict[str, object],
    runtime_status: dict[str, str] | None = None,
) -> None:
    """Reject a signed Studio mode mismatch before any provider is initialized."""
    status = runtime_status or provider_runtime_status()
    expected_provider = token_payload.get("provider_mode_constraint")
    if expected_provider is not None and expected_provider != status["provider_mode"]:
        raise ProviderModeConstraintError("Signed provider mode constraint mismatch.")
    expected_transcript = token_payload.get("stt_transcript_mode_constraint")
    if (
        expected_transcript is not None
        and expected_transcript != status["stt_transcript_mode"]
    ):
        raise ProviderModeConstraintError(
            "Signed STT transcript mode constraint mismatch."
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
    token_payload: dict[str, object],
    *,
    mint_context: MintContext | None = None,
    stt_provider: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    tts_provider: str | None = None,
    tts_voice_id: str | None = None,
) -> PipelineSessionConfig:
    """Load and authenticate the immutable plan pinned when the session was minted."""
    session_id = str(token_payload["sub"])
    tenant_id = str(token_payload["tenant_id"])
    agent_id = str(token_payload["agent_id"])
    ctx = mint_context or get_default_mint_context()
    session = await ctx.session_repo.get_session(tenant_id, session_id)
    if session is None:
        raise SessionPlanLoadError("Pinned session was not found.")
    if str(session.tenant_id) != tenant_id or str(session.agent_id) != agent_id:
        raise SessionPlanLoadError("Session identity does not match signed claims.")
    if not isinstance(session.runtime_plan_snapshot, dict):
        raise SessionPlanLoadError("Pinned runtime plan snapshot is missing.")

    try:
        plan = RuntimeSessionPlan.from_snapshot(session.runtime_plan_snapshot)
    except SessionPlanIntegrityError as exc:
        raise SessionPlanLoadError(str(exc)) from exc

    expected = {
        "tenant_id": (plan.tenant_id, tenant_id),
        "agent_id": (plan.agent_id, agent_id),
        "session_plan_ref": (plan.plan_id, token_payload.get("session_plan_ref")),
        "session_plan_hash": (plan.plan_hash, token_payload.get("session_plan_hash")),
        "agent_config_version": (
            plan.agent_version,
            token_payload.get("agent_config_version"),
        ),
    }
    for field_name, (actual, claimed) in expected.items():
        if str(actual) != str(claimed):
            raise SessionPlanLoadError(
                f"Pinned runtime plan {field_name} does not match signed claims."
            )
    if session.runtime_plan_hash != plan.plan_hash:
        raise SessionPlanLoadError("Pinned runtime plan hash does not match session.")
    if session.config_version_id != plan.plan_id:
        raise SessionPlanLoadError(
            "Pinned runtime plan reference does not match session."
        )
    if bool(token_payload.get("unsafe_demo", False)) != plan.unsafe_demo:
        raise SessionPlanLoadError("Unsafe plan status does not match signed claims.")

    language = str(
        token_payload.get("session_language") or session.session_language or ""
    )
    voice_id = str(
        token_payload.get("session_voice_id") or session.session_voice_id or ""
    )
    if session.session_language != language or session.session_voice_id != voice_id:
        raise SessionPlanLoadError("Session selection does not match signed claims.")
    try:
        selection = plan.select(language=language, voice_id=voice_id)
    except ValueError as exc:
        raise SessionPlanLoadError(str(exc)) from exc

    unsafe_overrides = unsafe_session_overrides_enabled()
    config = PipelineSessionConfig.from_runtime_plan(
        session_id=session_id,
        plan=plan,
        selection=selection,
        allow_unsafe_session_overrides=unsafe_overrides,
    )
    if unsafe_overrides:
        if stt_provider:
            config.stt_provider = stt_provider
        if llm_provider:
            config.llm_provider = llm_provider
        if llm_model:
            config.llm_model = llm_model
        if tts_provider:
            config.tts_provider = tts_provider
        if tts_voice_id:
            config.tts_voice_id = tts_voice_id
    return config


@app.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return

    try:
        payload = verify_session_jwt(token)
        _enforce_provider_mode_constraint(payload)
        remaining = max(1, int(float(payload["exp"]) - time.time()))
        token_store = getattr(websocket.app.state, "token_store", _default_token_store)
        claimed = await token_store.claim_connection(
            str(payload["tenant_id"]), str(payload["jti"]), remaining
        )
    except ProviderModeConstraintError:
        await websocket.close(code=4403, reason="provider mode mismatch")
        return
    except (KeyError, ReplayStoreUnavailableError, TypeError, ValueError):
        await websocket.close(code=4401, reason="invalid token")
        return
    if not claimed:
        await websocket.close(code=4401, reason="invalid token")
        return

    transport = NativeWebSocketTransport()
    ok = await transport.connect("ws", token)
    if not ok:
        await websocket.close(code=4401, reason="invalid token")
        return

    await websocket.accept()
    transport.bind(websocket)

    try:
        overrides = validate_demo_provider_overrides(
            {
                "stt_provider": websocket.query_params.get("stt_provider"),
                "llm_provider": websocket.query_params.get("llm_provider"),
                "llm_model": websocket.query_params.get("llm_model"),
                "tts_provider": websocket.query_params.get("tts_provider"),
                "tts_voice_id": websocket.query_params.get("tts_voice_id"),
            }
        )
        config = await _load_session_config(
            payload,
            stt_provider=overrides.get("stt_provider"),
            llm_provider=overrides.get("llm_provider"),
            llm_model=overrides.get("llm_model"),
            tts_provider=overrides.get("tts_provider"),
            tts_voice_id=overrides.get("tts_voice_id"),
        )
    except WSSecurityViolation as exc:
        await transport.send_control_event(
            "error",
            {"code": "PROVIDER_OVERRIDE_FORBIDDEN", "message": str(exc)},
        )
        await websocket.close(code=4403, reason="provider override forbidden")
        return
    except Exception:
        await websocket.close(code=4401, reason="invalid session")
        return

    async def _on_audio_out(pcm_bytes: bytes) -> None:
        await transport.send_audio_frame(pcm_bytes)

    async def _on_transcript(speaker: str, text: str) -> None:
        await transport.send_control_event(
            "transcript.final", {"speaker": speaker, "text": text}
        )

    orchestrator = PipelineOrchestrator(
        on_audio_out=_on_audio_out,
        on_transcript=_on_transcript,
    )
    try:
        await session_admission.acquire(config.session_id, config.tenant_id)
    except (AdmissionStoreUnavailableError, CapacityExceededError):
        await transport.close(websocket)
        return

    raw_rate = websocket.query_params.get("sample_rate") or websocket.query_params.get(
        "rate"
    )
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
        release_admission=lambda: session_admission.release(
            config.session_id, config.tenant_id
        ),
        heartbeat_admission=lambda: session_admission.heartbeat(
            config.session_id, config.tenant_id
        ),
        token_expires_at=(float(payload["exp"]) if payload.get("exp") else None),
    )
    try:
        await runner.start()
    except (ProtocolSessionError, WebSocketDisconnect):
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
