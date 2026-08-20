"""UCVE Provider Chain & Agent Configuration Schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderChainConfig(BaseModel):
    """Priority chain configuration for a specific provider category and language."""

    category: str
    language: str = "en"
    priority: list[str] = Field(default_factory=list)


class AgentProviderConfig(BaseModel):
    """Complete provider chain mapping for an agent session."""

    chains: list[ProviderChainConfig] = Field(default_factory=list)
    allow_testing_providers: bool = False
