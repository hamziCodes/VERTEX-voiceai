"""UCVE Secret Vaulting & Key Management Package."""

from __future__ import annotations

from core.secrets import (
    cache,
    envelope,
    exceptions,
    hmac,
    kms,
    platform,
    policy,
    repository,
    vault,
)
from core.secrets.cache import CredentialCacheKey, SecretCache
from core.secrets.envelope import EnvelopeEncryption
from core.secrets.exceptions import (
    DecryptionError,
    KMSBackendError,
    SecretNotFoundError,
)
from core.secrets.hmac import HMACSecretManager
from core.secrets.kms import KMSBackend
from core.secrets.platform import EnvironmentPlatformSecretProvider, PlatformCredential
from core.secrets.policy import CredentialTier, ResolvedCredential
from core.secrets.repository import (
    CredentialRecord,
    InMemorySecretRepository,
    SecretRepository,
)
from core.secrets.vault import PlatformSecrets, SecretVault

__all__ = [
    "cache",
    "envelope",
    "exceptions",
    "hmac",
    "kms",
    "platform",
    "policy",
    "repository",
    "vault",
    "SecretVault",
    "PlatformSecrets",
    "SecretCache",
    "CredentialCacheKey",
    "CredentialTier",
    "ResolvedCredential",
    "CredentialRecord",
    "SecretRepository",
    "InMemorySecretRepository",
    "PlatformCredential",
    "EnvironmentPlatformSecretProvider",
    "EnvelopeEncryption",
    "HMACSecretManager",
    "KMSBackend",
    "SecretNotFoundError",
    "DecryptionError",
    "KMSBackendError",
]
