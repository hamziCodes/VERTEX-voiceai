"""UCVE HMAC Secret Hash & Constant-Time Verification Layer."""

from __future__ import annotations

import hashlib
import hmac
import os

from core.runtime.env import is_production, is_test_env


class HMACSecretManager:
    """Manager for hash-only HMAC secret storage and verification."""

    @staticmethod
    def resolve_salt(salt: str | None = None, tenant_id: str | None = None) -> str:
        """Resolve per-tenant or env salt; refuse global default in production."""
        if salt:
            return salt
        env_salt = (os.environ.get("UCVE_HMAC_SALT") or "").strip()
        if env_salt:
            if tenant_id:
                return f"{env_salt}:{tenant_id}"
            return env_salt
        if tenant_id and not is_production():
            return f"ucve-hmac-salt:{tenant_id}"
        if is_test_env():
            return "ucve-hmac-salt"
        if is_production():
            raise RuntimeError(
                "UCVE_HMAC_SALT (or explicit per-tenant salt) required in production."
            )
        return "ucve-hmac-salt"

    @staticmethod
    def hash_secret(
        raw_secret: str, salt: str | None = None, tenant_id: str | None = None
    ) -> str:
        """Hash raw HMAC secret using SHA-256 for hash-only DB storage."""
        if not raw_secret:
            raise ValueError("HMAC secret cannot be empty.")
        resolved = HMACSecretManager.resolve_salt(salt, tenant_id=tenant_id)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            raw_secret.encode("utf-8"),
            resolved.encode("utf-8"),
            iterations=100000,
        )
        return derived.hex()

    @staticmethod
    def verify_secret(
        raw_secret: str,
        stored_hash: str,
        salt: str | None = None,
        tenant_id: str | None = None,
    ) -> bool:
        """Verify raw secret against stored hash using constant-time comparison."""
        if not raw_secret or not stored_hash:
            return False
        computed_hash = HMACSecretManager.hash_secret(
            raw_secret, salt=salt, tenant_id=tenant_id
        )
        return hmac.compare_digest(computed_hash, stored_hash)
