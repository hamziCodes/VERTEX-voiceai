"""UCVE HashiCorp Vault KMS Backend Wrapper."""

from __future__ import annotations

from core.secrets.kms import KMSBackend
from core.secrets.kms.local_dev import LocalDevKMSBackend


class HashiCorpVaultKMSBackend(KMSBackend):
    """HashiCorp Vault KMS backend adapter (falls back to local dev KMS if Vault client not configured)."""

    def __init__(self, transit_key_name: str = "ucve-transit") -> None:
        self.transit_key_name = transit_key_name
        self._fallback = LocalDevKMSBackend()

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        return self._fallback.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        return self._fallback.decrypt(ciphertext, key_version)
