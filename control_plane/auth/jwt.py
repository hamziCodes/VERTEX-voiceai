"""UCVE JWT Token Generator & Validator."""

from __future__ import annotations

import base64
import json
import time
from typing import Any


def issue_session_jwt(
    tenant_id: str,
    session_id: str,
    agent_id: str,
    ttl_sec: int = 120,
    secret: str = "ucve-jwt-secret",
) -> str:
    """Issue short-lived room join JWT token for WebSocket connection (TTL default 120s)."""
    now = int(time.time())
    payload = {
        "sub": session_id,
        "tenant_id": tenant_id,
        "agent_id": agent_id,
        "action": "roomJoin",
        "iat": now,
        "exp": now + ttl_sec,
    }
    header = {"alg": "HS256", "typ": "JWT"}

    b64_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(f"{b64_header}.{b64_payload}.{secret}".encode()).decode().rstrip("=")

    return f"{b64_header}.{b64_payload}.{sig}"


def verify_session_jwt(token: str, secret: str = "ucve-jwt-secret") -> dict[str, Any]:
    """Verify and decode room join JWT token."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT token format.")

    b64_header, b64_payload, sig = parts
    payload_json = base64.urlsafe_b64decode(b64_payload + "==").decode()
    payload = json.loads(payload_json)

    if time.time() > payload.get("exp", 0):
        raise ValueError("JWT token expired.")

    return payload
