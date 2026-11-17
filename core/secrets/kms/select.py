"""Choose the envelope-encryption KMS backend from configuration.

``UCVE_KMS_BACKEND`` selects it explicitly:

* ``local`` (default): Fernet keyed by ``UCVE_MASTER_KEY``. Production refuses
  to start without an explicit master key.
* ``aws``: AWS KMS (``AWS_KMS_KEY_ID``, ``AWS_REGION``, standard AWS
  credentials). Fails closed if boto3 or the key is unavailable.

The backend is never switched implicitly: secrets encrypted by one backend
cannot be decrypted by the other, so changing it requires re-encrypting the
stored credentials.
"""

from __future__ import annotations

import os

from core.secrets.kms import KMSBackend

SUPPORTED_BACKENDS = ("local", "aws")


class KMSConfigurationError(RuntimeError):
    """Raised when the configured KMS backend is unknown or incomplete."""


def kms_backend_from_environment() -> KMSBackend:
    name = (os.getenv("UCVE_KMS_BACKEND") or "local").strip().lower()
    if name == "local":
        from core.secrets.kms.local_dev import LocalDevKMSBackend

        return LocalDevKMSBackend()
    if name == "aws":
        if not (os.getenv("AWS_KMS_KEY_ID") or "").strip():
            raise KMSConfigurationError(
                "UCVE_KMS_BACKEND=aws requires AWS_KMS_KEY_ID."
            )
        from core.secrets.kms.aws_kms import AWSKMSBackend

        return AWSKMSBackend()
    raise KMSConfigurationError(
        f"UCVE_KMS_BACKEND must be one of {', '.join(SUPPORTED_BACKENDS)}."
    )
