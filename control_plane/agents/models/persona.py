"""UCVE Agent Builder - Persona Configuration Model."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersonaConfig(BaseModel):
    """Vocal personality, system prompt, and greeting configuration."""

    model_config = ConfigDict(extra="forbid")

    system_prompt: str = Field(
        default="You are Vertex Voice AI, a helpful, natural, concise voice assistant.",
        description="Core behavioral and conversational directives for the AI persona.",
    )
    greeting: str | None = Field(
        default=None,
        description="Optional opening speech synthesized upon call connect.",
    )
    voice_id: str = Field(
        default="default",
        description="Vocal timbre / voice ID for synthesis (e.g. cartesia sonic voice ID).",
    )
    voice_by_language: dict[str, str] = Field(
        default_factory=dict,
        description="Optional published language-to-voice bindings.",
    )
    persona_isolation: bool = Field(
        default=True,
        description="Whether persona prompts are isolated in tenant data classification boundary.",
    )
