"""UCVE Control Plane FastAPI application."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from inspect import isawaitable
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from control_plane.audit_routes import handle_get_audit_logs
from control_plane.auth.api_keys_async import build_api_key_manager
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission
from control_plane.auth.hmac_mint import expected_signature
from control_plane.auth.rate_limit import RateLimiter
from control_plane.middleware.security_headers import SecurityHeadersMiddleware
from control_plane.openapi_serve import register_self_hosted_docs
from control_plane.routes.agents import router as agents_router
from control_plane.routes.alerts import router as alerts_router
from control_plane.routes.privacy import router as privacy_router
from control_plane.routes.api_keys import router as api_keys_router
from control_plane.routes.conversations import router as conversations_router
from control_plane.routes.extraction_schemas import router as extraction_router
from control_plane.routes.identity import router as identity_router
from control_plane.routes.knowledge_bases import router as kb_router
from control_plane.routes.platform import router as platform_router
from control_plane.routes.provider_credentials import router as credentials_router
from control_plane.routes.session import (
    MintContext,
    get_default_mint_context,
    handle_session_mint,
    handle_session_refresh,
)
from control_plane.routes.studio import router as studio_router
from control_plane.routes.telephony import router as telephony_router
from control_plane.routes.usage import query_usage
from control_plane.secrets_routes import handle_rotate_secret, set_secret_vault
from control_plane.studio.pg_repository import PostgresStudioRepository
from control_plane.studio.repository import InMemoryStudioRepository
from control_plane.telephony_settings import (
    InMemoryTelephonySettingsRepository,
    PostgresTelephonySettingsRepository,
)
from core.db.async_pg import get_default_database
from core.alerts.service import build_alert_service, set_process_alert_service
from core.db.repos.privacy_repo import PostgresPrivacyJobRepository
from core.db.pg import use_memory_repos
from core.runtime.health import (
    CheckResult,
    ReadinessProbe,
    database_check,
    install_health_routes,
    profile_check,
    provider_configuration_check,
    redis_check,
)
from core.observability.http import (
    install_observability,
    observability_runtime,
    render_metrics,
)
from core.db.repos.post_call_repo import (
    InMemoryPostCallRepository,
    PostgresPostCallRepository,
)
from core.runtime.env import (
    get_ucve_env,
    is_protected_environment,
    require_production_secrets,
)
from core.secrets.repository import PostgresSecretRepository
from core.secrets.vault import SecretVault, build_secret_vault
from post_call.jobs.repository import (
    InMemoryPostCallJobRepository,
    PostgresPostCallJobRepository,
)


class QuickMintBody(BaseModel):
    tenant_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        min_length=1,
        max_length=128,
    )
    agent_id: str = Field(
        default="00000000-0000-0000-0000-0000000000a1",
        min_length=1,
        max_length=128,
    )
    language: str | None = Field(default=None, max_length=32)
    voice_id: str | None = Field(default=None, max_length=255)


class StudioMintBody(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    language: str | None = Field(default=None, max_length=32)
    voice_id: str | None = Field(default=None, max_length=255)
    test_mode: Literal["offline", "mock", "live"] = "offline"


class RotateSecretBody(BaseModel):
    tenant_id: str
    provider_id: str
    new_secret: str = Field(min_length=1)


class RefreshBody(BaseModel):
    token: str = Field(min_length=1, max_length=4096)


UsageReader = Annotated[AuthContext, Depends(require_permission("usage:read"))]
AuditReader = Annotated[AuthContext, Depends(require_permission("audit:read"))]
SecretRotator = Annotated[AuthContext, Depends(require_permission("secret:rotate"))]
SessionMinter = Annotated[AuthContext, Depends(require_permission("session:mint"))]


def _mint_secret() -> str:
    return (os.environ.get("UCVE_MINT_HMAC_SECRET") or "dev-mint-secret").strip()


def _metrics_bearer() -> str:
    return (os.environ.get("UCVE_METRICS_BEARER") or "").strip()


def _demo_mode() -> bool:
    """Allow unauthenticated /mint in local development demo mode."""
    if get_ucve_env() not in {"development", "dev", "test"}:
        return False
    explicit = os.environ.get("UCVE_DEMO_MODE")
    if explicit is not None:
        return explicit.strip() == "1"
    return get_ucve_env() in ("development", "dev")


def _allowed_origins() -> list[str]:
    raw = (os.environ.get("UCVE_ALLOWED_ORIGINS") or "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with observability_runtime(app, "control-plane"):
        async with _control_plane_lifespan(app):
            yield


@asynccontextmanager
async def _control_plane_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    require_production_secrets()
    from control_plane.auth.oidc_jwks import build_oidc_provider_from_environment

    oidc_provider = build_oidc_provider_from_environment()
    if oidc_provider is not None and not hasattr(app.state, "oidc_provider"):
        app.state.oidc_provider = oidc_provider
    database = None
    if not use_memory_repos():
        database = get_default_database()
        await database.open()
    app.state.mint_ctx = get_default_mint_context()
    app.state.auth_endpoint_limiter = RateLimiter(limit_per_min=60)
    if not hasattr(app.state, "api_keys"):
        app.state.api_keys = build_api_key_manager()
    app.state.api_keys.assert_runtime_ready(get_ucve_env())
    app.state.database = database
    app.state.db_pool = database.pool if database is not None else None
    app.state.studio_repository = (
        PostgresStudioRepository(database)
        if database is not None
        else InMemoryStudioRepository()
    )
    if database is not None:
        app.state.post_call_repository = PostgresPostCallRepository(database)
        app.state.post_call_job_repository = PostgresPostCallJobRepository(database)
        app.state.telephony_settings_repository = (
            PostgresTelephonySettingsRepository(database)
        )
        app.state.secret_vault = SecretVault(
            repository=PostgresSecretRepository(database)
        )
    else:
        call_repository = InMemoryPostCallRepository()
        app.state.post_call_repository = call_repository
        app.state.post_call_job_repository = InMemoryPostCallJobRepository(
            call_repository
        )
        app.state.telephony_settings_repository = (
            InMemoryTelephonySettingsRepository()
        )
        app.state.secret_vault = build_secret_vault()
    set_secret_vault(app.state.secret_vault)
    app.state.redis = None
    app.state.alert_service = build_alert_service(database)
    app.state.privacy_repository = (
        PostgresPrivacyJobRepository(database) if database is not None else None
    )
    app.state.mint_ctx.alerts = app.state.alert_service
    set_process_alert_service(app.state.alert_service)
    outbound_runtime = None
    if database is not None and not hasattr(app.state, "outbound_call_service"):
        from telephony_gateway.outbound_runtime import build_outbound_runtime

        outbound_runtime = build_outbound_runtime(database)
        if outbound_runtime is not None:
            app.state.outbound_call_service = outbound_runtime.service
    try:
        yield
    finally:
        if outbound_runtime is not None:
            await outbound_runtime.close()
            if (
                getattr(app.state, "outbound_call_service", None)
                is outbound_runtime.service
            ):
                delattr(app.state, "outbound_call_service")
        if database is not None:
            await database.close()


app = FastAPI(
    title="Wavia Voice AI — Control Plane", version="0.1.0", lifespan=lifespan
)

app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telephony_router, prefix="/v1")
app.include_router(extraction_router, prefix="/v1")
app.include_router(kb_router, prefix="/v1")
app.include_router(alerts_router, prefix="/v1")
app.include_router(identity_router)
app.include_router(platform_router)
app.include_router(studio_router)
app.include_router(agents_router)
app.include_router(conversations_router)
app.include_router(api_keys_router)
app.include_router(credentials_router)
app.include_router(privacy_router)

register_self_hosted_docs(app)

web_client_path = Path(__file__).resolve().parent.parent / "examples" / "web-client"
if web_client_path.exists():
    app.mount(
        "/demo", StaticFiles(directory=str(web_client_path), html=True), name="demo"
    )


@app.middleware("http")
async def request_id_and_tenant_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = (
        getattr(request.state, "request_id", None)
        or request.headers.get("x-request-id")
        or str(uuid.uuid4())
    )
    request.state.request_id = request_id
    auth_paths = {
        "/mint",
        "/v1/session",
        "/v1/session/mint",
        "/v1/session/refresh",
    }
    if request.url.path in auth_paths:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                request_size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request metadata."},
                    headers={"X-Request-Id": request_id},
                )
            if request_size > 8192:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Authentication request is too large."},
                    headers={"X-Request-Id": request_id},
                )
        peer = request.client.host if request.client else "unknown"
        limiter = getattr(request.app.state, "auth_endpoint_limiter", None)
        if limiter is not None and not limiter.is_allowed(f"auth-peer:{peer}"):
            return JSONResponse(
                status_code=429,
                content={"detail": "Authentication rate limit exceeded."},
                headers={"X-Request-Id": request_id, "Retry-After": "60"},
            )
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


install_observability(app, "control-plane")


async def _identity_check() -> CheckResult:
    configured = getattr(app.state, "oidc_provider", None) is not None
    if configured:
        return CheckResult.ok("identity", "OIDC provider configured")
    if is_protected_environment():
        return CheckResult.fail("identity", "OIDC provider not configured")
    return CheckResult.ok("identity", "OIDC not configured (development)")


readiness = ReadinessProbe("control-plane")
readiness.add_check(
    "database", database_check(lambda: getattr(app.state, "database", None))
)
readiness.add_check("redis", redis_check())
readiness.add_check("runtime_profile", profile_check)
readiness.add_check("identity", _identity_check)
readiness.add_check("providers", provider_configuration_check, required=False)
install_health_routes(app, readiness)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "control-plane"}


@app.get("/")
async def root() -> RedirectResponse:
    """Browser / tooling probes hit `/`; send humans to the demo console."""
    return RedirectResponse(url="/demo/", status_code=307)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    """Silence browser favicon requests to avoid 404 log noise."""
    return Response(status_code=204, media_type="image/x-icon")


@app.get("/json/version")
async def json_version() -> dict[str, str]:
    """Chrome/CDP-style probes often hit this on open ports — avoid noisy 404s."""
    return {
        "service": "ucve-control-plane",
        "version": app.version or "0.1.0",
        "note": "Not a Chrome DevTools endpoint",
    }


@app.post("/v1/session")
async def mint_session(
    request: Request,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id", min_length=1, max_length=128),
    x_timestamp: str = Header(..., alias="X-Timestamp", min_length=1, max_length=32),
    x_nonce: str = Header(..., alias="X-Nonce", min_length=8, max_length=255),
    x_agent_id: str = Header(..., alias="X-Agent-Id", min_length=1, max_length=128),
    x_signature: str = Header(..., alias="X-Signature", min_length=64, max_length=128),
    origin: str | None = Header(None, alias="Origin"),
    referer: str | None = Header(None, alias="Referer"),
    authorization: str | None = Header(None, alias="Authorization"),
    x_language: str | None = Header(None, alias="X-Language"),
    x_voice_id: str | None = Header(None, alias="X-Voice-Id"),
) -> JSONResponse:
    ctx: MintContext = (
        getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    )
    api_key_mint = False
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        try:
            verified = request.app.state.api_keys.verify_api_key(
                raw, required_scope="session:mint"
            )
            record = await verified if isawaitable(verified) else verified
            if str(record["tenant_id"]) != x_tenant_id:
                raise HTTPException(status_code=403, detail="Tenant context mismatch.")
            api_key_mint = True
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    status, body = await handle_session_mint(
        x_tenant_id,
        x_timestamp,
        x_nonce,
        x_agent_id,
        x_signature,
        secret=_mint_secret(),
        origin=origin,
        referer=referer,
        api_key_mint=api_key_mint,
        ctx=ctx,
        requested_language=x_language,
        requested_voice_id=x_voice_id,
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("error", "mint failed"))

    extra_headers = body.pop("_headers", {}) or {}
    return JSONResponse(content=body, headers=extra_headers)


@app.post("/mint")
@app.post("/v1/session/mint")
async def quick_mint_session(
    body: QuickMintBody,
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
) -> JSONResponse:
    """Mint a demo session using local demo mode or API-key authentication."""
    api_key_mint = False
    if _demo_mode():
        api_key_mint = True
    elif authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        try:
            verified = request.app.state.api_keys.verify_api_key(
                raw, required_scope="session:mint"
            )
            record = await verified if isawaitable(verified) else verified
            if str(record["tenant_id"]) != body.tenant_id:
                raise HTTPException(status_code=403, detail="Tenant context mismatch.")
            api_key_mint = True
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=401, detail="Authentication required for /mint")

    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    secret = _mint_secret()
    sig = expected_signature(secret, body.tenant_id, ts, nonce, body.agent_id)
    ctx: MintContext = (
        getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    )
    status, res_body = await handle_session_mint(
        body.tenant_id,
        ts,
        nonce,
        body.agent_id,
        sig,
        secret=secret,
        api_key_mint=api_key_mint,
        ctx=ctx,
        requested_language=body.language,
        requested_voice_id=body.voice_id,
    )
    if status != 200:
        raise HTTPException(
            status_code=status, detail=res_body.get("error", "mint failed")
        )
    extra_headers = res_body.pop("_headers", {}) or {}
    return JSONResponse(content=res_body, headers=extra_headers)


@app.post("/v1/studio/sessions")
async def studio_mint_session(
    body: StudioMintBody,
    request: Request,
    auth: SessionMinter,
) -> JSONResponse:
    """Mint a short-lived room token for an authenticated Studio workspace."""
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex
    secret = _mint_secret()
    signature = expected_signature(
        secret, auth.tenant_id, timestamp, nonce, body.agent_id
    )
    ctx: MintContext = (
        getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    )
    status, payload = await handle_session_mint(
        auth.tenant_id,
        timestamp,
        nonce,
        body.agent_id,
        signature,
        secret=secret,
        api_key_mint=True,
        ctx=ctx,
        requested_language=body.language,
        requested_voice_id=body.voice_id,
        requested_provider_mode="live" if body.test_mode == "live" else "mock",
        requested_stt_transcript_mode=(
            "fixed_mock" if body.test_mode == "mock" else None
        ),
    )
    if status != 200:
        raise HTTPException(
            status_code=status,
            detail=payload.get("error", "mint failed"),
        )
    extra_headers = payload.pop("_headers", {}) or {}
    return JSONResponse(content=payload, headers=extra_headers)


@app.post("/v1/session/refresh")
async def refresh_session(body: RefreshBody, request: Request) -> dict[str, Any]:
    ctx: MintContext = (
        getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    )
    status, payload = await handle_session_refresh(body.token, ctx=ctx)
    if status != 200:
        raise HTTPException(
            status_code=status, detail=payload.get("error", "refresh failed")
        )
    return payload


@app.get("/v1/usage")
async def get_usage(
    request: Request,
    auth: UsageReader,
) -> dict[str, Any]:
    tenant_id = auth.tenant_id
    mint_ctx: MintContext = request.app.state.mint_ctx
    status, body = await query_usage(
        tenant_id,
        tenant_id,
        repository=mint_ctx.quota.repository,
        admission=mint_ctx.admission,
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("error"))
    return body


@app.get("/v1/audit")
async def get_audit(
    auth: AuditReader,
) -> dict[str, Any]:
    tenant_id = auth.tenant_id
    status, body = await handle_get_audit_logs(
        tenant_id, tenant_id, actor_role=auth.primary_role
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("error"))
    return body


@app.post("/v1/secrets/rotate")
async def rotate_secret(
    body: RotateSecretBody,
    auth: SecretRotator,
) -> dict[str, Any]:
    enforce_tenant_access(auth, body.tenant_id)
    status, payload = await handle_rotate_secret(
        body.tenant_id, body.provider_id, body.new_secret
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=payload.get("error"))
    return payload


@app.get("/metrics")
async def metrics(
    authorization: str | None = Header(None, alias="Authorization"),
) -> PlainTextResponse:
    return render_metrics(authorization)
