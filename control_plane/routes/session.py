"""UCVE Session Mint & Refresh Control-Plane Route Handlers."""

from __future__ import annotations

from typing import Any

from control_plane.auth.hmac_mint import verify_mint_signature
from control_plane.auth.jwt import issue_session_jwt, verify_session_jwt
from control_plane.auth.rate_limit import RateLimiter

_rate_limiter = RateLimiter(limit_per_min=120)


def handle_session_mint(
    tenant_id: str,
    ts: str,
    nonce: str,
    agent_id: str,
    signature: str,
    secret: str = "dev-mint-secret",
) -> tuple[int, dict[str, Any]]:
    """POST /v1/session — HMAC-authenticated room mint endpoint."""
    if not _rate_limiter.is_allowed(tenant_id):
        return 429, {"error": "Rate limit exceeded (120 req/min)."}

    if not verify_mint_signature(secret, tenant_id, ts, nonce, agent_id, signature):
        return 401, {"error": "Invalid or expired mint signature."}

    session_id = f"sess_{nonce[:8]}"
    jwt_token = issue_session_jwt(tenant_id, session_id, agent_id)

    return 200, {
        "status": "success",
        "session_id": session_id,
        "token": jwt_token,
        "ttl_sec": 120,
    }


def handle_session_refresh(token: str) -> tuple[int, dict[str, Any]]:
    """POST /v1/session/refresh — Refresh short-lived room token."""
    try:
        payload = verify_session_jwt(token)
        new_token = issue_session_jwt(
            payload["tenant_id"], payload["sub"], payload["agent_id"]
        )
        return 200, {"status": "success", "token": new_token, "ttl_sec": 120}
    except Exception as exc:
        return 401, {"error": str(exc)}
