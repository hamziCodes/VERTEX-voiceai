"""Telnyx Webhook Ed25519 / HMAC Signature Validator — Fail Closed."""

from __future__ import annotations

import base64
import binascii
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def verify_telnyx_signature(
    payload_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    public_key_or_secret: str | None = None,
    public_key: str | None = None,
    hmac_secret: str | None = None,
    max_drift_sec: float = 300.0,
    now: float | None = None,
) -> bool:
    """Verify Telnyx Ed25519 over ``timestamp + b"|" + raw_body``.

    The legacy HMAC argument remains in the call signature only so old callers fail
    closed during migration. It is never accepted by the carrier verifier.
    """
    del hmac_secret
    pk = public_key or public_key_or_secret
    if not signature_header or not timestamp_header or not pk:
        return False
    try:
        if not timestamp_header.isascii() or not timestamp_header.isdigit():
            return False
        timestamp = int(timestamp_header)
        current = time.time() if now is None else now
        if max_drift_sec <= 0 or abs(current - timestamp) > max_drift_sec:
            return False
        raw_key = base64.b64decode(pk, validate=True)
        raw_signature = base64.b64decode(signature_header, validate=True)
        if len(raw_key) != 32 or len(raw_signature) != 64:
            return False
        signed_payload = timestamp_header.encode("ascii") + b"|" + payload_body
        Ed25519PublicKey.from_public_bytes(raw_key).verify(
            raw_signature, signed_payload
        )
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        return False
    return True
