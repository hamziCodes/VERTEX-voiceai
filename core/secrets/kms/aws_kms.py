"""UCVE AWS KMS Backend Wrapper."""

from __future__ import annotations

import os

from core.runtime.env import is_production
from core.secrets.exceptions import DecryptionError
from core.secrets.kms import KMSBackend


class KMSNotConfigured(RuntimeError):
    """Raised when AWS KMS is required but boto3/key is unavailable."""


class AWSKMSBackend(KMSBackend):
    """AWS KMS backend via boto3. Never silently Fernet-falls-back in production."""

    def __init__(self, key_id: str | None = None) -> None:
        self.key_id = key_id or os.environ.get("AWS_KMS_KEY_ID") or "alias/ucve-master-key"
        self._client = None
        try:
            import boto3

            self._client = boto3.client(
                "kms", region_name=os.environ.get("AWS_REGION", "us-east-1")
            )
        except Exception as exc:
            if is_production():
                raise KMSNotConfigured(
                    "AWS KMS boto3 client required when UCVE_ENV=production."
                ) from exc
            raise KMSNotConfigured(
                "AWS KMS not configured; refuse LocalDev Fernet fallback from AWSKMSBackend."
            ) from exc

    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        if self._client is None:
            raise KMSNotConfigured("AWS KMS client not available.")
        resp = self._client.encrypt(KeyId=self.key_id, Plaintext=plaintext)
        return resp["CiphertextBlob"], 1

    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        if self._client is None:
            raise KMSNotConfigured("AWS KMS client not available.")
        try:
            resp = self._client.decrypt(CiphertextBlob=ciphertext)
            return resp["Plaintext"]
        except Exception as exc:
            raise DecryptionError(f"AWS KMS decrypt failed: {exc}") from exc
