"""UCVE HashiCorp Vault KMS Backend Wrapper."""

from __future__ import annotations

from core.secrets.kms import KMSBackend
from core.secrets.kms.aws_kms import KMSNotConfigured


class HashiCorpVaultKMSBackend(KMSBackend):
    """HashiCorp Vault transit — not configured yet; fail closed (no Fernet fallback)."""

    def __init__(self, transit_key_name: str = "ucve-transit") -> None:
        self.transit_key_name = transit_key_name
        raise KMSNotConfigured(
            "HashiCorp Vault KMS is not implemented yet; configure AWS KMS or LocalDev in non-prod."
        )

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        raise KMSNotConfigured("Vault KMS not configured.")

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        raise KMSNotConfigured("Vault KMS not configured.")
