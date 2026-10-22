"""Strict short-lived JWT contract for worker WebSocket admission."""

from __future__ import annotations

import os
import time
import uuid
from typing import Any

import jwt

from core.runtime.env import (
    KNOWN_INSECURE_DEFAULTS,
    is_protected_environment,
)

_TEST_DEFAULT_SECRET = "ucve-jwt-secret-test-only-32bytes!"
_REQUIRED_ACTION = "roomJoin"
_TOKEN_TYPE = "session_access"
_DEFAULT_ISSUER = "wavia-control-plane"
_DEFAULT_AUDIENCE = "wavia-worker"
_MAX_TTL_SEC = 300


class JWTConfigurationError(ValueError):
    """Raised when JWT signing configuration cannot be resolved safely."""


def jwt_issuer() -> str:
    return (os.environ.get("UCVE_JWT_ISSUER") or _DEFAULT_ISSUER).strip()


def jwt_audience() -> str:
    return (os.environ.get("UCVE_JWT_AUDIENCE") or _DEFAULT_AUDIENCE).strip()


def resolve_jwt_secret(secret: str | None = None) -> str:
    """Resolve an HS256 secret and reject defaults in protected environments."""
    resolved = (secret or os.environ.get("UCVE_JWT_SECRET") or "").strip()
    if not resolved and not is_protected_environment():
        return _TEST_DEFAULT_SECRET
    insecure = (
        resolved.lower() in KNOWN_INSECURE_DEFAULTS or resolved == _TEST_DEFAULT_SECRET
    )
    if not resolved or (is_protected_environment() and insecure):
        raise JWTConfigurationError("Secure JWT signing configuration is required.")
    return resolved


def issue_session_jwt(
    tenant_id: str,
    session_id: str,
    agent_id: str,
    ttl_sec: int = 120,
    secret: str | None = None,
    *,
    session_plan_ref: str | None = None,
    session_plan_hash: str | None = None,
    agent_config_version: int | None = None,
    session_language: str | None = None,
    session_voice_id: str | None = None,
    unsafe_demo: bool = False,
) -> str:
    """Issue one short-lived, single-connection room token."""
    if not tenant_id or not session_id or not agent_id:
        raise ValueError("Session token identity is incomplete.")
    if ttl_sec <= 0 or ttl_sec > _MAX_TTL_SEC:
        raise ValueError("Session token TTL is outside the allowed range.")
    signing_secret = resolve_jwt_secret(secret)
    iat = int(time.time())
    payload: dict[str, Any] = {
        "sub": session_id,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "action": _REQUIRED_ACTION,
        "token_type": _TOKEN_TYPE,
        "iss": jwt_issuer(),
        "aud": jwt_audience(),
        "jti": str(uuid.uuid4()),
        "iat": iat,
        "exp": iat + ttl_sec,
    }
    optional_claims = {
        "session_plan_ref": session_plan_ref,
        "session_plan_hash": session_plan_hash,
        "agent_config_version": agent_config_version,
        "session_language": session_language,
        "session_voice_id": session_voice_id,
    }
    payload.update(
        {key: value for key, value in optional_claims.items() if value is not None}
    )
    if unsafe_demo:
        payload["unsafe_demo"] = True
    return jwt.encode(payload, signing_secret, algorithm="HS256")


def verify_session_jwt(token: str, secret: str | None = None) -> dict[str, Any]:
    """Verify signature, routing claims, token type, issuer, and audience."""
    signing_secret = resolve_jwt_secret(secret)
    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=["HS256"],
            issuer=jwt_issuer(),
            audience=jwt_audience(),
            options={
                "require": [
                    "exp",
                    "iat",
                    "iss",
                    "aud",
                    "jti",
                    "sub",
                    "tenant_id",
                    "agent_id",
                    "action",
                    "token_type",
                ]
            },
        )
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid session token.") from exc

    if payload.get("action") != _REQUIRED_ACTION:
        raise ValueError("Invalid session token.")
    if payload.get("token_type") != _TOKEN_TYPE:
        raise ValueError("Invalid session token.")
    if not all(payload.get(name) for name in ("sub", "tenant_id", "agent_id", "jti")):
        raise ValueError("Invalid session token.")
    return payload
