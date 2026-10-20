"""UCVE JWT Token Generator & Validator (PyJWT HS256)."""

from __future__ import annotations

import os
import time
from typing import Any

import jwt

from core.runtime.env import is_production, is_test_env

_TEST_DEFAULT_SECRET = "ucve-jwt-secret-test-only-32bytes!"
_REQUIRED_ACTION = "roomJoin"


class JWTConfigurationError(ValueError):
    """Raised when JWT signing secret cannot be resolved safely."""


def resolve_jwt_secret(secret: str | None = None) -> str:
    """Resolve HS256 secret: explicit arg → env → test/dev default."""
    if secret:
        return secret
    env_secret = (os.environ.get("UCVE_JWT_SECRET") or "").strip()
    if env_secret:
        return env_secret
    if not is_production():
        return _TEST_DEFAULT_SECRET
    raise JWTConfigurationError(
        "UCVE_JWT_SECRET is required when UCVE_ENV is 'production'."
    )


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
    """Issue short-lived roomJoin JWT (HS256, default TTL 120s)."""
    signing_secret = resolve_jwt_secret(secret)
    iat = int(time.time())
    payload = {
        "sub": session_id,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "action": _REQUIRED_ACTION,
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
    """Verify signature + exp and require action == roomJoin."""
    signing_secret = resolve_jwt_secret(secret)
    try:
        payload = jwt.decode(
            token,
            signing_secret,
            algorithms=["HS256"],
            options={
                "require": [
                    "exp",
                    "iat",
                    "sub",
                    "tenant_id",
                    "agent_id",
                    "action",
                ]
            },
        )
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("JWT token expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid JWT token: {exc}") from exc

    if payload.get("action") != _REQUIRED_ACTION:
        raise ValueError("JWT action must be 'roomJoin'.")
    return payload
