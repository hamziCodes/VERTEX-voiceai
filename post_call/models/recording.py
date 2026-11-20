"""Call Recording Data Model — Audio artifact metadata & dual-channel defaults."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RecordingState(StrEnum):
    NOT_REQUESTED = "not_requested"
    RECORDING = "recording"
    AVAILABLE = "available"
    FAILED = "failed"


class CallRecording(BaseModel):
    """Verified recording artifact metadata."""

    state: RecordingState = RecordingState.AVAILABLE
    recording_s3_uri: str | None = Field(
        default=None, description="Opaque object-store reference."
    )
    dual_channel: bool = Field(default=False)
    channel_count: int = Field(default=1, ge=1, le=2)
    duration_sec: float = Field(default=0.0, gt=0.0)
    checksum: str = Field(default="", pattern=r"^[0-9a-f]{64}$")
    storage_region: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def validate_storage_evidence(self) -> CallRecording:
        if self.state is not RecordingState.AVAILABLE:
            raise ValueError("CallRecording describes only available artifacts.")
        if not self.recording_s3_uri or not self.storage_region.strip():
            raise ValueError("Available recordings require object and region evidence.")
        if self.dual_channel != (self.channel_count == 2):
            raise ValueError("dual_channel must match channel_count.")
        return self
