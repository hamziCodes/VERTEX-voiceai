"""Stage 3: readiness must fail when a live chain route has no credential."""

from __future__ import annotations

import pytest

from control_plane.agents.credential_readiness import missing_route_credentials
from control_plane.agents.models.provider_config import AgentProvidersConfig
from core.secrets.platform import PlatformCredential
from core.secrets.policy import CredentialTier
from core.secrets.vault import SecretVault

ALL_DEFAULT_PROVIDERS = {
    "gladia",
    "deepgram",
    "groq",
    "gemini",
    "uplift",
    "cartesia",
    "elevenlabs",
}


class _Platform:
    def __init__(self, configured: set[str]) -> None:
        self.configured = configured

    def resolve(
        self, provider_id: str, credential_type: str
    ) -> PlatformCredential | None:
        return (
            PlatformCredential(secret="x") if provider_id in self.configured else None
        )


def _live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RUN_MOCK_PROVIDERS", raising=False)
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")


@pytest.mark.asyncio
async def test_a_fallback_route_without_a_key_blocks_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live(monkeypatch)
    vault = SecretVault(platform_secrets=_Platform(ALL_DEFAULT_PROVIDERS - {"gemini"}))
    issues = await missing_route_credentials(
        vault, "tenant", AgentProvidersConfig.create_default()
    )
    assert [i.code for i in issues] == ["provider_credential_missing"]
    assert "'gemini'" in issues[0].message
    assert issues[0].field == "providers.llm"


@pytest.mark.asyncio
async def test_fully_keyed_chain_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    _live(monkeypatch)
    vault = SecretVault(platform_secrets=_Platform(ALL_DEFAULT_PROVIDERS))
    assert (
        await missing_route_credentials(
            vault, "tenant", AgentProvidersConfig.create_default()
        )
        == []
    )


@pytest.mark.asyncio
async def test_mock_mode_needs_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "0")
    monkeypatch.setenv("UCVE_ENV", "test")
    vault = SecretVault(platform_secrets=_Platform(set()))
    assert (
        await missing_route_credentials(
            vault, "tenant", AgentProvidersConfig.create_default()
        )
        == []
    )


@pytest.mark.asyncio
async def test_presence_check_follows_tier_rules() -> None:
    vault = SecretVault(platform_secrets=_Platform({"groq"}))
    await vault.astore(
        "tenant", "openai", "sk-tenant", "api_key", credential_ref="mine"
    )

    async def has(provider: str, tier: CredentialTier, ref: str | None = None) -> bool:
        return await vault.has_credential(
            "tenant", provider, credential_ref=ref, tier=tier
        )

    assert await has("groq", CredentialTier.PLATFORM)
    assert not await has("groq", CredentialTier.BYOK, "mine")
    assert await has("openai", CredentialTier.BYOK, "mine")
    assert await has("openai", CredentialTier.BOTH, "mine")
    assert await has("groq", CredentialTier.BOTH, "missing-ref")
    assert not await has("openai", CredentialTier.PLATFORM)
