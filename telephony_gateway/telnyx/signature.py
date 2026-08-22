"""Telnyx Webhook Ed25519 / HMAC Signature Validator — Fail Closed."""

from __future__ import annotations

import base64
import hmac
import time


def verify_telnyx_signature(
    payload_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    public_key_or_secret: str | None = None,
    public_key: str | None = None,
    hmac_secret: str | None = None,
    max_drift_sec: float = 300.0,
) -> bool:
    """Validate incoming Telnyx webhook signature (fail-closed security)."""
    pk = public_key or public_key_or_secret
    sec = hmac_secret or public_key_or_secret

    if not signature_header or not timestamp_header or not (pk or sec):
        return False

    try:
        ts = float(timestamp_header)
        now = time.time()
        if abs(now - ts) > max_drift_sec:
            return False
    except ValueError:
        return False

    signed_payload = f"{timestamp_header}|".encode("utf-8") + payload_body

    # 1. Try Ed25519 if pk provided and valid base64 key of 32 bytes
    if pk:
        try:
            raw_key = base64.b64decode(pk)
            if len(raw_key) == 32:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

                key_obj = Ed25519PublicKey.from_public_bytes(raw_key)
                raw_sig = base64.b64decode(signature_header)
                key_obj.verify(raw_sig, signed_payload)
                return True
        except Exception:
            pass

    # 2. HMAC-SHA256 verification if secret provided
    if sec:
        try:
            computed_mac = hmac.new(
                sec.encode("utf-8"),
                signed_payload,
                "sha256",
            ).hexdigest()
            if hmac.compare_digest(computed_mac, signature_header):
                return True
            computed_b64 = base64.b64encode(
                hmac.new(
                    sec.encode("utf-8"),
                    signed_payload,
                    "sha256",
                ).digest()
            ).decode("utf-8")
            if hmac.compare_digest(computed_b64, signature_header):
                return True
        except Exception:
            pass

    return False
