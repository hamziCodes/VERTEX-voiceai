"""Immutable privacy policy captured when a call is admitted."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PostCallPolicy(BaseModel):
    """Privacy-first recording, retention, residency, and review policy."""

    model_config = ConfigDict(frozen=True)

    recording_enabled: bool = False
    recording_consent_obtained: bool = False
    transcript_retention_days: int = Field(default=30, ge=0, le=30)
    recording_retention_days: int = Field(default=7, ge=0, le=7)
    storage_region: str = Field(default="local", min_length=1, max_length=64)
    requires_review_for_external_actions: bool = True

    @model_validator(mode="after")
    def validate_recording_policy(self) -> PostCallPolicy:
        if self.recording_consent_obtained and not self.recording_enabled:
            raise ValueError("Recording consent cannot enable a disabled policy.")
        if not self.storage_region.strip():
            raise ValueError("A storage region is required.")
        return self
