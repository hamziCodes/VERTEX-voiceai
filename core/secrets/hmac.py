"""UCVE HMAC Secret Hash & Constant-Time Verification Layer."""

from __future__ import annotations

import hmac
import hashlib


class HMACSecretManager:
    """Manager for hash-only HMAC secret storage and verification."""

    @staticmethod
    def hash_secret(raw_secret: str, salt: str = "ucve-hmac-salt") -> str:
        """Hash raw HMAC secret using SHA-256 for hash-only DB storage."""
        if not raw_secret:
            raise ValueError("HMAC secret cannot be empty.")
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            raw_secret.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000,
        )
        return derived.hex()

    @staticmethod
    def verify_secret(raw_secret: str, stored_hash: str, salt: str = "ucve-hmac-salt") -> bool:
        """Verify raw secret against stored hash using constant-time comparison."""
        if not raw_secret or not stored_hash:
            return False
        computed_hash = HMACSecretManager.hash_secret(raw_secret, salt=salt)
        return hmac.compare_digest(computed_hash, stored_hash)
