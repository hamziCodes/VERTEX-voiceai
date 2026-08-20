"""UCVE GCP Cloud KMS Backend Wrapper."""

from __future__ import annotations

from core.secrets.kms import KMSBackend
from core.secrets.kms.aws_kms import KMSNotConfigured


class GCPKMSBackend(KMSBackend):
    """GCP Cloud KMS — not configured yet; fail closed (no Fernet fallback)."""

    def __init__(
        self,
        key_name: str = "projects/ucve/locations/global/keyRings/ucve/cryptoKeys/master",
    ) -> None:
        self.key_name = key_name
        raise KMSNotConfigured(
            "GCP KMS is not implemented yet; configure AWS KMS or LocalDev in non-prod."
        )

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        raise KMSNotConfigured("GCP KMS not configured.")

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        raise KMSNotConfigured("GCP KMS not configured.")
