"""UCVE Agent Builder - Provider Chain Configuration Models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderRoute(BaseModel):
    """Single vendor route in a priority chain."""

    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(description="Vendor provider identifier, e.g. 'groq', 'gemini', 'gladia', 'cartesia'.")
    model: str | None = Field(default=None, description="Optional model identifier, e.g. 'openai/gpt-oss-120b'.")
    credential_ref: str | None = Field(
        default=None,
        description="Tenant-vault reference; never a plaintext credential.",
    )
    enabled: bool = Field(default=True, description="Whether this route is currently active.")
    priority: int = Field(default=1, description="Priority ranking in failover order (1 = primary, 2 = secondary).")


class CategoryPriorityChain(BaseModel):
    """Priority chain for a single category and language."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="Provider category: 'stt', 'llm', 'tts', 's2s'.")
    language: str = Field(default="en", description="Target language code (e.g. 'en', 'ar', 'es').")
    routes: list[ProviderRoute] = Field(default_factory=list, description="Ordered failover routes.")

    def enabled_route_count(self) -> int:
        return sum(1 for r in self.routes if r.enabled)


class AgentProvidersConfig(BaseModel):
    """Multi-category provider priority chains for an agent."""

    model_config = ConfigDict(extra="forbid")

    stt: list[CategoryPriorityChain] = Field(default_factory=list)
    llm: list[CategoryPriorityChain] = Field(default_factory=list)
    tts: list[CategoryPriorityChain] = Field(default_factory=list)
    s2s: list[CategoryPriorityChain] = Field(default_factory=list)

    @classmethod
    def create_default(cls) -> AgentProvidersConfig:
        """Create standard resilient default provider chains (≥ 2 routes each)."""
        return cls(
            stt=[
                CategoryPriorityChain(
                    category="stt",
                    language="en",
                    routes=[
                        ProviderRoute(provider_id="gladia", priority=1, enabled=True),
                        ProviderRoute(provider_id="deepgram", priority=2, enabled=True),
                    ],
                )
            ],
            llm=[
                CategoryPriorityChain(
                    category="llm",
                    language="en",
                    routes=[
                        ProviderRoute(provider_id="groq", model="openai/gpt-oss-120b", priority=1, enabled=True),
                        ProviderRoute(provider_id="gemini", model="gemini-2.5-flash", priority=2, enabled=True),
                    ],
                )
            ],
            tts=[
                CategoryPriorityChain(
                    category="tts",
                    language="en",
                    routes=[
                        ProviderRoute(provider_id="cartesia", model="sonic-2", priority=1, enabled=True),
                        ProviderRoute(provider_id="uplift", model="orator", priority=2, enabled=True),
                    ],
                )
            ],
            s2s=[],
        )
