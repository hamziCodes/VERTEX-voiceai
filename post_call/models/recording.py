"""Call Recording Data Model — Audio artifact metadata & dual-channel defaults."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CallRecording(BaseModel):
    """Metadata for call recording audio artifact stored in Object Vault / S3."""

    recording_s3_uri: str = Field(..., description="S3/Vault URI, e.g. s3://bucket/tenant/recording.wav")
    dual_channel: bool = Field(default=True, description="True if agent & caller audio are separate channels")
    duration_sec: float = Field(default=0.0, ge=0.0, description="Audio recording duration in seconds")
    checksum: str = Field(default="", description="SHA-256 integrity checksum")
