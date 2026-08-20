"""UCVE Control-Plane Server-to-Server HMAC Mint Signature Authentication."""

from __future__ import annotations

import hashlib
import hmac
import time

from core.redis.nonce_store import NonceStore

__all__ = [
    "NonceStore",
    "expected_signature",
    "verify_mint_signature",
]


def expected_signature(
    secret: str, tenant_id: str, ts: str, nonce: str, agent_id: str
) -> str:
    """Compute canonical HMAC-SHA256 hex signature over mint parameters (habiba pattern)."""
    payload = f"{tenant_id}.{ts}.{nonce}.{agent_id}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_mint_signature(
    secret: str,
    tenant_id: str,
    ts: str,
    nonce: str,
    agent_id: str,
    signature: str,
    max_age_sec: int = 60,
) -> bool:
    """Verify HMAC signature and timestamp freshness window."""
    try:
        ts_float = float(ts)
    except (ValueError, TypeError):
        return False

    now = time.time()
    if abs(now - ts_float) > max_age_sec:
        return False

    expected = expected_signature(secret, tenant_id, ts, nonce, agent_id)
    return hmac.compare_digest(expected, signature)
