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

    def validate_chains(self, tenant_allow_testing: bool = False) -> None:
        """Validate resilience rules (>= 2 providers per chain) and testing provider permissions."""
        from core.providers.exceptions import ConfigurationError

        effective_allow_testing = self.allow_testing_providers or tenant_allow_testing

        for chain in self.chains:
            if len(chain.priority) < 2:
                raise ConfigurationError(
                    f"Priority chain for category '{chain.category}' and language '{chain.language}' must have at least 2 enabled providers for resilience. Got {len(chain.priority)}."
                )
            if not effective_allow_testing:
                for provider_id in chain.priority:
                    if provider_id.startswith(("test_", "mock_", "null_")):
                        raise ConfigurationError(
                            f"Testing provider '{provider_id}' is not allowed for this tenant (allow_testing_providers is False)."
                        )

