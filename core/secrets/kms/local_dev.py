"""UCVE Local Development KMS Backend Implementation."""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet

from core.runtime.env import is_production
from core.secrets.exceptions import DecryptionError
from core.secrets.kms import KMSBackend


class LocalDevKMSBackend(KMSBackend):
    """Local development KMS backend using Fernet derived from UCVE_MASTER_KEY.

    Forbidden as the sole KMS when UCVE_ENV=production (no default master key).
    """

    def __init__(self, master_key: str | None = None) -> None:
        if is_production() and master_key is None and not os.getenv("UCVE_MASTER_KEY"):
            raise RuntimeError(
                "LocalDevKMSBackend refuses to start without an explicit master key "
                "when UCVE_ENV=production; configure AWS KMS instead."
            )
        raw_key = master_key or os.getenv("UCVE_MASTER_KEY")
        if not raw_key:
            if is_production():
                raise RuntimeError(
                    "UCVE_MASTER_KEY must not be defaulted when UCVE_ENV=production."
                )
            # Dev/test only — explicit insecure fallback for local Fernet.
            raw_key = "ucve-dev-master-key-default-secret-32b"
        key_bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        self.fernet = Fernet(fernet_key)
        self.current_key_version = 1

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        ciphertext = self.fernet.encrypt(plaintext)
        return ciphertext, self.current_key_version

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        try:
            return self.fernet.decrypt(ciphertext)
        except Exception as exc:
            raise DecryptionError(f"Decryption failed: {exc}") from exc
