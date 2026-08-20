"""UCVE Secret Vaulting Exceptions."""

from __future__ import annotations


class SecretNotFoundError(Exception):
    """Raised when requested tenant secret or platform fallback credential is not found."""


class DecryptionError(Exception):
    """Raised when decryption fails due to invalid key, tampered payload, or corrupted blob."""


class KMSBackendError(Exception):
    """Raised when KMS key management service operation fails."""
