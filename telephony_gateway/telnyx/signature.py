"""Telnyx Webhook Ed25519 / HMAC Signature Validator — Fail Closed."""

from __future__ import annotations

import base64
import hmac
import time


def verify_telnyx_signature(
    payload_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    public_key_or_secret: str,
    max_drift_sec: float = 300.0,
) -> bool:
    """Validate incoming Telnyx webhook signature (fail-closed security).

    Validates that:
    1. Signature and timestamp headers are present.
    2. Timestamp is within max_drift_sec window of current epoch time.
    3. Ed25519 or HMAC-SHA256 signature matches signed payload string: `timestamp|payload`.
    """
    if not signature_header or not timestamp_header or not public_key_or_secret:
        return False

    try:
        ts = float(timestamp_header)
        now = time.time()
        if abs(now - ts) > max_drift_sec:
            return False
    except ValueError:
        return False

    signed_payload = f"{timestamp_header}|".encode("utf-8") + payload_body

    # Try Cryptography Ed25519 if installed
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        raw_key = base64.b64decode(public_key_or_secret)
        public_key = Ed25519PublicKey.from_public_bytes(raw_key)
        raw_sig = base64.b64decode(signature_header)
        public_key.verify(raw_sig, signed_payload)
        return True
    except Exception:
        pass

    # HMAC-SHA256 fallback for testing / symmetric secrets
    try:
        computed_mac = hmac.new(
            public_key_or_secret.encode("utf-8"),
            signed_payload,
            "sha256",
        ).hexdigest()
        if hmac.compare_digest(computed_mac, signature_header):
            return True
        # Also check base64 encoded MAC
        computed_b64 = base64.b64encode(
            hmac.new(
                public_key_or_secret.encode("utf-8"),
                signed_payload,
                "sha256",
            ).digest()
        ).decode("utf-8")
        if hmac.compare_digest(computed_b64, signature_header):
            return True
    except Exception:
        pass

    return False
