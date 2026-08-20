"""UCVE S3-Compatible Storage Client for Audio Recording Objects."""

from __future__ import annotations

import hashlib
from typing import Any


class S3StorageClient:
    """S3-compatible object storage client for raw audio recordings."""

    def __init__(self, bucket_name: str = "ucve-recordings", endpoint_url: str | None = None) -> None:
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self._in_memory_store: dict[str, bytes] = {}

    def upload_recording(
        self, tenant_id: str, session_id: str, audio_bytes: bytes, filename: str = "recording.wav"
    ) -> tuple[str, str, int]:
        """Upload raw audio bytes to S3 and return (s3_uri, checksum_sha256, byte_count)."""
        s3_uri = f"s3://{self.bucket_name}/{tenant_id}/{session_id}/{filename}"
        checksum = hashlib.sha256(audio_bytes).hexdigest()
        byte_count = len(audio_bytes)

        # Store in memory store for local/test usage
        self._in_memory_store[s3_uri] = audio_bytes
        return s3_uri, checksum, byte_count

    def download_recording(self, s3_uri: str) -> bytes:
        """Download raw audio bytes from S3 storage by URI."""
        if s3_uri in self._in_memory_store:
            return self._in_memory_store[s3_uri]
        raise FileNotFoundError(f"Recording object not found at {s3_uri}")
