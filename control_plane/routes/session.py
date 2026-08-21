"""UCVE Session Mint & Refresh Control-Plane Route Handlers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from control_plane.auth.hmac_mint import verify_mint_signature
from control_plane.auth.jwt import issue_session_jwt, verify_session_jwt
from control_plane.auth.rate_limit import RateLimiter
from core.db.models import Session, Tenant
from core.db.repos.session_repo import SessionRepository
from core.db.repos.tenant_repo import TenantRepository
from core.metering.quota_enforcer import QuotaEnforcer
from core.redis.nonce_store import NonceStore
from core.types.ids import generate_session_id


from core.db.repos.pg_repos import (
    build_session_repository,
    build_tenant_repository,
)


@dataclass
class MintContext:
    """Injectable dependencies for session mint."""

    nonce_store: NonceStore = field(default_factory=NonceStore)
    tenant_repo: Any = field(default_factory=build_tenant_repository)
    session_repo: Any = field(default_factory=build_session_repository)
    quota: QuotaEnforcer = field(default_factory=QuotaEnforcer)
    rate_limiter: RateLimiter = field(default_factory=lambda: RateLimiter(limit_per_min=120))
    mint_rejections: list[dict[str, Any]] = field(default_factory=list)
    audit_events: list[dict[str, Any]] = field(default_factory=list)


_default_ctx = MintContext()


def get_default_mint_context() -> MintContext:
    return _default_ctx


def reset_default_mint_context() -> MintContext:
    global _default_ctx
    _default_ctx = MintContext()
    return _default_ctx


def _origin_host(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "://" not in raw:
        return raw.lower().rstrip("/")
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path
    return host.lower().rstrip("/") if host else None


def _origin_allowed(allowed: list[str], origin: str | None, referer: str | None) -> bool:
    if not allowed:
        return True
    allowed_hosts = {_origin_host(a) for a in allowed if _origin_host(a)}
    for candidate in (origin, referer):
        host = _origin_host(candidate)
        if host and host in allowed_hosts:
            return True
        # Also allow exact string match against configured origins
        if candidate and candidate.rstrip("/") in {a.rstrip("/") for a in allowed}:
            return True
    return False


def _record_rejection(
    ctx: MintContext,
    tenant_id: str | None,
    status: int,
    reason: str,
) -> None:
    event = {"tenant_id": tenant_id, "status": status, "reason": reason}
    ctx.mint_rejections.append(event)
    ctx.audit_events.append({"action": "mint_rejected", **event})


async def handle_session_mint(
    tenant_id: str,
    ts: str,
    nonce: str,
    agent_id: str,
    signature: str,
    secret: str = "dev-mint-secret",
    *,
    origin: str | None = None,
    referer: str | None = None,
    api_key_mint: bool = False,
    ctx: MintContext | None = None,
    current_concurrent: int = 0,
    current_monthly_minutes: float = 0.0,
    jwt_secret: str | None = None,
) -> tuple[int, dict[str, Any]]:
    """POST /v1/session — HMAC-authenticated room mint endpoint."""
    mint_ctx = ctx or _default_ctx
    headers: dict[str, str] = {}

    if not mint_ctx.rate_limiter.is_allowed(tenant_id):
        _record_rejection(mint_ctx, tenant_id, 429, "rate limited")
        return 429, {"error": "Rate limit exceeded (120 req/min)."}

    if not verify_mint_signature(secret, tenant_id, ts, nonce, agent_id, signature):
        _record_rejection(mint_ctx, tenant_id, 401, "invalid or expired mint signature")
        return 401, {"error": "Invalid or expired mint signature."}

    if await mint_ctx.nonce_store.is_used(tenant_id, nonce):
        _record_rejection(mint_ctx, tenant_id, 401, "nonce replay")
        return 401, {"error": "Nonce replay rejected."}

    tenant = await mint_ctx.tenant_repo.get_tenant(tenant_id)
    if tenant is None:
        # Auto-provision only for isolated unit tests that omit seeding.
        # Production/H2 path must pre-create tenants.
        if os.environ.get("UCVE_ENV", "development").lower() == "test":
            tenant = Tenant(id=tenant_id, name=f"test-{tenant_id}")
            await mint_ctx.tenant_repo.create_tenant(tenant)
        else:
            _record_rejection(mint_ctx, tenant_id, 401, "unknown tenant")
            return 401, {"error": "Unknown tenant."}

    try:
        agent = await mint_ctx.tenant_repo.get_agent_for_tenant(tenant_id, agent_id)
    except PermissionError:
        _record_rejection(mint_ctx, tenant_id, 403, "cross-tenant agent")
        return 403, {"error": "Agent does not belong to tenant."}

    if agent is None:
        if os.environ.get("UCVE_ENV", "development").lower() == "test":
            from core.db.models import Agent

            agent = Agent(id=agent_id, tenant_id=tenant_id, name=agent_id)
            await mint_ctx.tenant_repo.save_agent(agent)
        else:
            _record_rejection(mint_ctx, tenant_id, 403, "agent not found")
            return 403, {"error": "Agent does not belong to tenant."}

    if not api_key_mint and not _origin_allowed(tenant.allowed_origins, origin, referer):
        _record_rejection(mint_ctx, tenant_id, 403, "origin not allowed")
        return 403, {"error": "Origin not allowed."}

    quota_result = await mint_ctx.quota.check_mint(
        tenant_id,
        current_concurrent=current_concurrent,
        current_monthly_minutes=current_monthly_minutes,
    )
    if not quota_result.allowed:
        _record_rejection(mint_ctx, tenant_id, 429, quota_result.reason or "quota")
        return 429, {"error": quota_result.reason or "Quota exceeded."}
    if quota_result.is_soft_cap_warn:
        headers["X-UCVE-Quota-Warning"] = "soft_cap"

    await mint_ctx.nonce_store.mark_used(tenant_id, nonce, ttl_sec=60)

    session_id = str(generate_session_id())
    session = Session(id=session_id, tenant_id=tenant_id, agent_id=agent_id)
    await mint_ctx.session_repo.create_session(tenant_id, session)

    token = issue_session_jwt(tenant_id, session_id, agent_id, secret=jwt_secret)
    mint_ctx.quota.acquire(tenant_id, session_id)
    ws_url = os.environ.get("UCVE_WS_PUBLIC_URL", "ws://localhost:8081/ws/audio")

    body: dict[str, Any] = {
        "status": "success",
        "session_id": session_id,
        "token": token,
        "ttl_sec": 120,
        "ws_url": ws_url,
    }
    if headers:
        body["_headers"] = headers
    mint_ctx.audit_events.append(
        {
            "action": "session_minted",
            "tenant_id": tenant_id,
            "session_id": session_id,
            "agent_id": agent_id,
        }
    )
    return 200, body


def handle_session_refresh(
    token: str, jwt_secret: str | None = None
) -> tuple[int, dict[str, Any]]:
    """POST /v1/session/refresh — Refresh short-lived room token."""
    try:
        payload = verify_session_jwt(token, secret=jwt_secret)
        new_token = issue_session_jwt(
            payload["tenant_id"],
            payload["sub"],
            payload["agent_id"],
            secret=jwt_secret,
        )
        return 200, {"status": "success", "token": new_token, "ttl_sec": 120}
    except Exception as exc:
        return 401, {"error": str(exc)}
