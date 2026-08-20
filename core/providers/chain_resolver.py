"""UCVE Priority Chain Resolver & Capability Table Join."""

from __future__ import annotations

from core.providers.config_schema import AgentProviderConfig, ProviderChainConfig
from core.providers.exceptions import ConfigurationError


class ChainResolver:
    """Resolves and validates provider priority chains for agent sessions."""

    @staticmethod
    def resolve_chain(
        category: str,
        language: str,
        config: AgentProviderConfig,
    ) -> list[str]:
        """Resolve ordered provider IDs for category and language, validating resilience requirements."""
        target_chain: ProviderChainConfig | None = None
        for chain in config.chains:
            if chain.category == category and chain.language == language:
                target_chain = chain
                break

        if not target_chain:
            # Fallback to category default with language='en' or any match
            for chain in config.chains:
                if chain.category == category:
                    target_chain = chain
                    break

        if not target_chain or len(target_chain.priority) < 2:
            count = len(target_chain.priority) if target_chain else 0
            raise ConfigurationError(
                f"Priority chain for category '{category}' and language '{language}' must have at least 2 enabled providers for resilience. Got {count}."
            )

        return list(target_chain.priority)
