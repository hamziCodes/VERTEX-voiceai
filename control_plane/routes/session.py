"""UCVE Session Mint & Refresh Control-Plane Route Handlers."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from control_plane.agents.compiler import (
    SessionPlanCompilationError,
    build_unsafe_demo_plan,
    compile_agent_version_async,
)
from control_plane.agents.repo import get_default_agent_config_repo
from control_plane.auth.hmac_mint import verify_mint_signature
from control_plane.auth.jwt import issue_session_jwt, verify_session_jwt
from control_plane.auth.rate_limit import RateLimiter
from core.db.models import Session, Tenant
from core.db.repos.pg_repos import (
    build_session_repository,
    build_tenant_repository,
)
from core.metering.quota_enforcer import QuotaEnforcer
from core.redis.nonce_store import NonceStore, ReplayStoreUnavailableError
from core.redis.token_store import SessionTokenStore
from core.runtime.admission import (
    AdmissionStoreUnavailableError,
    CapacityExceededError,
    SessionAdmissionController,
)
from core.types.ids import generate_session_id


@dataclass
class MintContext:
    """Injectable dependencies for session mint."""

    nonce_store: NonceStore = field(default_factory=NonceStore)
    token_store: SessionTokenStore = field(default_factory=SessionTokenStore)
    tenant_repo: Any = field(default_factory=build_tenant_repository)
    session_repo: Any = field(default_factory=build_session_repository)
    agent_config_repo: Any = field(default_factory=get_default_agent_config_repo)
    quota: QuotaEnforcer = field(default_factory=QuotaEnforcer)
    rate_limiter: RateLimiter = field(
        default_factory=lambda: RateLimiter(limit_per_min=120)
    )
    admission: SessionAdmissionController = field(
        default_factory=SessionAdmissionController
    )
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


def _origin_allowed(
    allowed: list[str], origin: str | None, referer: str | None
) -> bool:
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


def unsafe_session_overrides_enabled() -> bool:
    """Return True only for an explicitly enabled local development/test process."""

    environment = (os.environ.get("UCVE_ENV") or "development").strip().lower()
    enabled = os.environ.get("UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES", "0") == "1"
    return environment in {"development", "dev", "test"} and enabled


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
    requested_language: str | None = None,
    requested_voice_id: str | None = None,
    requested_provider_mode: str | None = None,
    requested_stt_transcript_mode: str | None = None,
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

    try:
        nonce_claimed = await mint_ctx.nonce_store.consume_once(
            tenant_id, nonce, ttl_sec=60
        )
    except ReplayStoreUnavailableError:
        _record_rejection(mint_ctx, tenant_id, 503, "replay store unavailable")
        return 503, {"error": "Authentication service temporarily unavailable."}
    if not nonce_claimed:
        _record_rejection(mint_ctx, tenant_id, 401, "nonce replay")
        return 401, {"error": "Nonce replay rejected."}

    tenant = await mint_ctx.tenant_repo.get_tenant(tenant_id)
    if tenant is None:
        # Auto-provision for test or development mode when seeding demo tenant.
        if os.environ.get("UCVE_ENV", "development").lower() in ("test", "development"):
            tenant = Tenant(id=tenant_id, name=f"dev-{tenant_id}")
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
        if os.environ.get("UCVE_ENV", "development").lower() in ("test", "development"):
            from core.db.models import Agent

            agent = Agent(id=agent_id, tenant_id=tenant_id, name=agent_id)
            await mint_ctx.tenant_repo.save_agent(agent)
        else:
            _record_rejection(mint_ctx, tenant_id, 403, "agent not found")
            return 403, {"error": "Agent does not belong to tenant."}

    if not api_key_mint and not _origin_allowed(
        tenant.allowed_origins, origin, referer
    ):
        _record_rejection(mint_ctx, tenant_id, 403, "origin not allowed")
        return 403, {"error": "Origin not allowed."}

    try:
        plan = await compile_agent_version_async(
            tenant_id,
            agent_id,
            None,
            repo=mint_ctx.agent_config_repo,
        )
    except SessionPlanCompilationError as exc:
        if (
            exc.code == "PUBLISHED_CONFIG_NOT_FOUND"
            and unsafe_session_overrides_enabled()
        ):
            plan = build_unsafe_demo_plan(
                tenant_id,
                agent_id,
                system_prompt=getattr(agent, "system_prompt", ""),
            )
        else:
            _record_rejection(mint_ctx, tenant_id, 409, exc.code)
            return 409, {
                "error": "A valid published agent configuration is required.",
                "code": "PUBLISHED_CONFIG_REQUIRED",
            }

    try:
        selection = plan.select(
            language=requested_language,
            voice_id=requested_voice_id,
        )
    except ValueError as exc:
        _record_rejection(mint_ctx, tenant_id, 422, "invalid session selection")
        return 422, {
            "error": str(exc),
            "code": "SESSION_SELECTION_INVALID",
        }

    try:
        durable_concurrent = await mint_ctx.admission.current_tenant_count(tenant_id)
    except AdmissionStoreUnavailableError:
        _record_rejection(mint_ctx, tenant_id, 503, "admission unavailable")
        return 503, {"error": "Session admission is temporarily unavailable."}
    quota_result = await mint_ctx.quota.check_mint(
        tenant_id,
        current_concurrent=durable_concurrent,
        current_monthly_minutes=current_monthly_minutes,
    )
    if not quota_result.allowed:
        _record_rejection(mint_ctx, tenant_id, 429, quota_result.reason or "quota")
        return 429, {"error": quota_result.reason or "Quota exceeded."}
    if quota_result.is_soft_cap_warn:
        headers["X-UCVE-Quota-Warning"] = "soft_cap"

    session_id = str(generate_session_id())
    try:
        await mint_ctx.admission.acquire(
            session_id,
            tenant_id,
            max_tenant_sessions=quota_result.max_concurrent,
        )
    except CapacityExceededError as exc:
        _record_rejection(mint_ctx, tenant_id, 503, str(exc))
        return 503, {"error": "Worker capacity limit reached. Please retry shortly."}
    except AdmissionStoreUnavailableError:
        _record_rejection(mint_ctx, tenant_id, 503, "admission unavailable")
        return 503, {"error": "Session admission is temporarily unavailable."}

    session = Session(
        id=session_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        compliance_tier=plan.compliance_tier,  # type: ignore[arg-type]
        config_version_id=plan.plan_id,
        agent_config_version=plan.agent_version,
        runtime_plan_hash=plan.plan_hash,
        runtime_plan_snapshot=plan.to_snapshot(),
        session_language=selection.language,
        session_voice_id=selection.voice_id,
        pinned_at=datetime.now(UTC),
    )
    try:
        await mint_ctx.session_repo.create_session(tenant_id, session)
        token = issue_session_jwt(
            tenant_id,
            session_id,
            agent_id,
            secret=jwt_secret,
            session_plan_ref=plan.plan_id,
            session_plan_hash=plan.plan_hash,
            agent_config_version=plan.agent_version,
            session_language=selection.language,
            session_voice_id=selection.voice_id,
            provider_mode_constraint=requested_provider_mode,
            stt_transcript_mode_constraint=requested_stt_transcript_mode,
            unsafe_demo=plan.unsafe_demo,
        )
    except Exception:
        await mint_ctx.admission.release(session_id, tenant_id)
        raise
    mint_ctx.quota.acquire(tenant_id, session_id)
    ws_url = os.environ.get("UCVE_WS_PUBLIC_URL", "ws://localhost:8081/ws/audio")

    body: dict[str, Any] = {
        "status": "success",
        "session_id": session_id,
        "token": token,
        "ttl_sec": 120,
        "ws_url": ws_url,
        "agent_config_version": plan.agent_version,
        "session_plan_ref": plan.plan_id,
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


async def handle_session_refresh(
    token: str,
    jwt_secret: str | None = None,
    *,
    ctx: MintContext | None = None,
) -> tuple[int, dict[str, Any]]:
    """POST /v1/session/refresh — Refresh short-lived room token."""
    mint_ctx = ctx or _default_ctx
    try:
        payload = verify_session_jwt(token, secret=jwt_secret)
        tenant_id = str(payload["tenant_id"])
        session_id = str(payload["sub"])
        agent_id = str(payload["agent_id"])
        session = await mint_ctx.session_repo.get_session(tenant_id, session_id)
        if session is None or str(session.agent_id) != agent_id:
            raise ValueError("Session identity mismatch.")
        remaining = max(1, int(float(payload["exp"]) - time.time()))
        consumed = await mint_ctx.token_store.consume_refresh(
            tenant_id, str(payload["jti"]), remaining
        )
        if not consumed:
            raise ValueError("Token refresh already consumed.")
        new_token = issue_session_jwt(
            tenant_id,
            session_id,
            agent_id,
            secret=jwt_secret,
            session_plan_ref=payload.get("session_plan_ref"),
            session_plan_hash=payload.get("session_plan_hash"),
            agent_config_version=payload.get("agent_config_version"),
            session_language=payload.get("session_language"),
            session_voice_id=payload.get("session_voice_id"),
            provider_mode_constraint=payload.get("provider_mode_constraint"),
            stt_transcript_mode_constraint=payload.get(
                "stt_transcript_mode_constraint"
            ),
            unsafe_demo=bool(payload.get("unsafe_demo", False)),
        )
        return 200, {"status": "success", "token": new_token, "ttl_sec": 120}
    except (KeyError, PermissionError, ReplayStoreUnavailableError, ValueError):
        return 401, {"error": "Invalid or unavailable session token."}
