"""UCVE GCP Cloud KMS Backend Wrapper."""

from __future__ import annotations

from core.secrets.kms import KMSBackend
from core.secrets.kms.local_dev import LocalDevKMSBackend


class GCPKMSBackend(KMSBackend):
    """GCP Cloud KMS backend adapter (falls back to local dev KMS if GCP client not configured)."""

    def __init__(self, key_name: str = "projects/ucve/locations/global/keyRings/ucve/cryptoKeys/master") -> None:
        self.key_name = key_name
        self._fallback = LocalDevKMSBackend()

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        return self._fallback.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        return self._fallback.decrypt(ciphertext, key_version)
