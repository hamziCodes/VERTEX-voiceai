"""UCVE Control Plane FastAPI application."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from control_plane.audit_routes import handle_get_audit_logs
from control_plane.auth.api_keys import APIKeyManager
from control_plane.auth.middleware import enforce_rbac
from control_plane.metrics import handle_metrics_request
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
from core.runtime.env import require_production_secrets


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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    require_production_secrets()
    app.state.mint_ctx = get_default_mint_context()
    app.state.api_keys = APIKeyManager()
    app.state.db_pool = None
    app.state.redis = None
    yield


app = FastAPI(title="UCVE Control Plane", version="0.1.0", lifespan=lifespan)

app.include_router(telephony_router, prefix="/v1")
app.include_router(extraction_router, prefix="/v1")
app.include_router(kb_router, prefix="/v1")
app.include_router(alerts_router, prefix="/v1")


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
    ctx: MintContext = request.app.state.mint_ctx
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


@app.post("/v1/session/refresh")
async def refresh_session(body: RefreshBody) -> dict[str, Any]:
    status, payload = handle_session_refresh(body.token)
    if status != 200:
        raise HTTPException(status_code=status, detail=payload.get("error", "refresh failed"))
    return payload


async def require_tenant_context(
    request: Request,
    x_tenant_id: str | None = Header(None, alias="X-Tenant-Id"),
    x_actor_role: str = Header("tenant_viewer", alias="X-Actor-Role"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> tuple[str, str]:
    """Resolve tenant from API key or membership headers."""
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization.split(" ", 1)[1].strip()
        if raw.startswith("ucve_live_"):
            try:
                rec = request.app.state.api_keys.verify_api_key(raw)
            except PermissionError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc
            return str(rec["tenant_id"]), x_actor_role
    if not x_tenant_id:
        raise HTTPException(status_code=401, detail="X-Tenant-Id required")
    return x_tenant_id, x_actor_role


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
