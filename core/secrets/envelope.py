"""UCVE Envelope Encryption & Key Versioning Layer."""

from __future__ import annotations

import base64

from core.secrets.kms import KMSBackend
from core.secrets.kms.select import kms_backend_from_environment


class EnvelopeEncryption:
    """Envelope encryption helper utilizing pluggable KMS backend."""

    def __init__(self, kms_backend: KMSBackend | None = None) -> None:
        self.kms = kms_backend or kms_backend_from_environment()

    def encrypt_secret(self, secret: str) -> tuple[str, int]:
        """Encrypt secret string and return (base64_encrypted_blob, key_version)."""
        plaintext = secret.encode("utf-8")
        ciphertext_bytes, key_version = self.kms.encrypt(plaintext)
        encoded_blob = base64.b64encode(ciphertext_bytes).decode("ascii")
        return encoded_blob, key_version

    def decrypt_secret(self, encrypted_blob: str, key_version: int = 1) -> str:
        """Decrypt base64_encrypted_blob and return plaintext secret string."""
        ciphertext_bytes = base64.b64decode(encrypted_blob.encode("ascii"))
        plaintext = self.kms.decrypt(ciphertext_bytes, key_version=key_version)
        return plaintext.decode("utf-8")
