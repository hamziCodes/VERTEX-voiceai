"""UCVE Control Plane FastAPI application."""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from control_plane.audit_routes import handle_get_audit_logs
from control_plane.auth.api_keys import APIKeyManager
from control_plane.auth.hmac_mint import expected_signature
from control_plane.auth.middleware import enforce_rbac
from control_plane.metrics import handle_metrics_request
from control_plane.routes.agents import router as agents_router
from control_plane.routes.alerts import router as alerts_router
from control_plane.routes.extraction_schemas import router as extraction_router
from control_plane.routes.knowledge_bases import router as kb_router
from control_plane.routes.session import (
    MintContext,
    get_default_mint_context,
    handle_session_mint,
    handle_session_refresh,
)
from control_plane.routes.telephony import router as telephony_router
from control_plane.routes.usage import handle_get_usage
from control_plane.secrets_routes import handle_rotate_secret
from core.runtime.env import get_ucve_env, require_production_secrets


class QuickMintBody(BaseModel):
    tenant_id: str = "00000000-0000-0000-0000-000000000001"
    agent_id: str = "00000000-0000-0000-0000-0000000000a1"


class RotateSecretBody(BaseModel):
    tenant_id: str
    provider_id: str
    new_secret: str = Field(min_length=1)


class RefreshBody(BaseModel):
    token: str


def _mint_secret() -> str:
    return (os.environ.get("UCVE_MINT_HMAC_SECRET") or "dev-mint-secret").strip()


def _metrics_bearer() -> str:
    return (os.environ.get("UCVE_METRICS_BEARER") or "").strip()


def _demo_mode() -> bool:
    """Allow unauthenticated /mint for local demo console (development only by default)."""
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
    require_production_secrets()
    app.state.mint_ctx = get_default_mint_context()
    app.state.api_keys = APIKeyManager()
    app.state.db_pool = None
    app.state.redis = None
    yield


from control_plane.middleware.security_headers import SecurityHeadersMiddleware

app = FastAPI(title="Wavia Voice AI — Control Plane", version="0.1.0", lifespan=lifespan)

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
app.include_router(agents_router)

from control_plane.openapi_serve import register_self_hosted_docs
register_self_hosted_docs(app)

from pathlib import Path
from fastapi.staticfiles import StaticFiles

web_client_path = Path(__file__).resolve().parent.parent / "examples" / "web-client"
if web_client_path.exists():
    app.mount("/demo", StaticFiles(directory=str(web_client_path), html=True), name="demo")



@app.middleware("http")
async def request_id_and_tenant_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.tenant_id = request.headers.get("x-tenant-id")
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


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
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_timestamp: str = Header(..., alias="X-Timestamp"),
    x_nonce: str = Header(..., alias="X-Nonce"),
    x_agent_id: str = Header(..., alias="X-Agent-Id"),
    x_signature: str = Header(..., alias="X-Signature"),
    origin: str | None = Header(None, alias="Origin"),
    referer: str | None = Header(None, alias="Referer"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> JSONResponse:
    ctx: MintContext = getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    api_key_mint = False
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        try:
            request.app.state.api_keys.verify_api_key(raw, required_scope="session:mint")
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
    """Developer helper endpoint for quick session minting (demo mode or API-key auth)."""
    api_key_mint = False
    if _demo_mode():
        api_key_mint = True
    elif authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        try:
            request.app.state.api_keys.verify_api_key(raw, required_scope="session:mint")
            api_key_mint = True
        except PermissionError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=401, detail="Authentication required for /mint")

    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    secret = _mint_secret()
    sig = expected_signature(secret, body.tenant_id, ts, nonce, body.agent_id)
    ctx: MintContext = getattr(request.app.state, "mint_ctx", None) or get_default_mint_context()
    status, res_body = await handle_session_mint(
        body.tenant_id,
        ts,
        nonce,
        body.agent_id,
        sig,
        secret=secret,
        api_key_mint=api_key_mint,
        ctx=ctx,
    )
    if status != 200:
        raise HTTPException(status_code=status, detail=res_body.get("error", "mint failed"))
    extra_headers = res_body.pop("_headers", {}) or {}
    return JSONResponse(content=res_body, headers=extra_headers)


@app.post("/v1/session/refresh")
async def refresh_session(body: RefreshBody) -> dict[str, Any]:
    status, payload = handle_session_refresh(body.token)
    if status != 200:
        raise HTTPException(status_code=status, detail=payload.get("error", "refresh failed"))
    return payload


async def require_tenant_context(
    request: Request,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    x_actor_role: str | None = Header(None, alias="X-Actor-Role"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> tuple[str, str]:
    """Resolve tenant and role from verified API key / JWT credentials only."""
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        if raw.startswith("ucve_live_"):
            try:
                rec = request.app.state.api_keys.verify_api_key(raw)
            except PermissionError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            role = str(rec.get("role") or "tenant_viewer")
            return str(rec["tenant_id"]), role
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    raise HTTPException(status_code=401, detail="Authorization required")


@app.get("/v1/usage")
async def get_usage(
    tenant: tuple[str, str] = Depends(require_tenant_context),
) -> dict[str, Any]:
    tenant_id, _role = tenant
    status, body = handle_get_usage(tenant_id, tenant_id)
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("error"))
    return body


@app.get("/v1/audit")
async def get_audit(
    tenant: tuple[str, str] = Depends(require_tenant_context),
) -> dict[str, Any]:
    tenant_id, role = tenant
    try:
        enforce_rbac(role, "audit", "read")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    status, body = handle_get_audit_logs(tenant_id, tenant_id, actor_role=role)
    if status != 200:
        raise HTTPException(status_code=status, detail=body.get("error"))
    return body


@app.post("/v1/secrets/rotate")
async def rotate_secret(
    body: RotateSecretBody,
    tenant: tuple[str, str] = Depends(require_tenant_context),
) -> dict[str, Any]:
    tenant_id, role = tenant
    try:
        enforce_rbac(role, "secret", "rotate")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if body.tenant_id != tenant_id and role != "platform_admin":
        raise HTTPException(status_code=403, detail="Cross-tenant secret rotate forbidden.")
    status, payload = handle_rotate_secret(body.tenant_id, body.provider_id, body.new_secret)
    if status != 200:
        raise HTTPException(status_code=status, detail=payload.get("error"))
    return payload


@app.get("/metrics")
async def metrics(
    authorization: str | None = Header(None, alias="Authorization"),
) -> PlainTextResponse:
    expected = _metrics_bearer()
    if not expected:
        raise HTTPException(status_code=503, detail="UCVE_METRICS_BEARER not configured.")
    if not authorization or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    code, headers, body = handle_metrics_request()
    return PlainTextResponse(content=body, status_code=code, headers=headers)
