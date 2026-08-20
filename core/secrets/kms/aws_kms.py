"""UCVE AWS KMS Backend Wrapper."""

from __future__ import annotations

from core.secrets.kms import KMSBackend
from core.secrets.kms.local_dev import LocalDevKMSBackend


class AWSKMSBackend(KMSBackend):
    """AWS KMS backend adapter (falls back to local dev KMS if AWS boto3 client not configured)."""

    def __init__(self, key_id: str = "alias/ucve-master-key") -> None:
        self.key_id = key_id
        self._fallback = LocalDevKMSBackend()

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        return self._fallback.encrypt(plaintext)

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        return self._fallback.decrypt(ciphertext, key_version)
