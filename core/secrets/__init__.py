"""UCVE Secret Vaulting & Key Management Package."""

from __future__ import annotations

from core.secrets import cache, envelope, exceptions, hmac, kms, vault
from core.secrets.cache import SecretCache
from core.secrets.envelope import EnvelopeEncryption
from core.secrets.exceptions import DecryptionError, KMSBackendError, SecretNotFoundError
from core.secrets.hmac import HMACSecretManager
from core.secrets.kms import KMSBackend
from core.secrets.vault import PlatformSecrets, SecretVault

__all__ = [
    "cache",
    "envelope",
    "exceptions",
    "hmac",
    "kms",
    "vault",
    "SecretVault",
    "PlatformSecrets",
    "SecretCache",
    "EnvelopeEncryption",
    "HMACSecretManager",
    "KMSBackend",
    "SecretNotFoundError",
    "DecryptionError",
    "KMSBackendError",
]
