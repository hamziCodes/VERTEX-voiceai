"""Diarized Turn Data Model — FSM state transition & speech turn breakdown."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiarizedTurn(BaseModel):
    """Represents a single speaker turn within a voice session."""

    speaker: str = Field(..., description="user / agent / system / assistant")
    text: str = Field(..., description="Transcribed or synthesized speech text")
    start_ms: int = Field(..., description="Epoch timestamp or session relative ms start")
    end_ms: int = Field(..., description="Epoch timestamp or session relative ms end")
    language: str = Field(default="en", description="BCP-47 language tag (e.g. en, ar, ms)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="STT/FSM confidence score")
