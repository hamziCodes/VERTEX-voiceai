"""UCVE KMS Backend Protocol & Interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class KMSBackend(ABC):
    """Abstract Base Class for pluggable KMS envelope encryption backends."""

    @abstractmethod
    def encrypt(self, plaintext: bytes) -> tuple[bytes, int]:
        """Encrypt plaintext bytes and return (ciphertext_bytes, key_version)."""

    @abstractmethod
    def decrypt(self, ciphertext: bytes, key_version: int = 1) -> bytes:
        """Decrypt ciphertext bytes given key_version."""
