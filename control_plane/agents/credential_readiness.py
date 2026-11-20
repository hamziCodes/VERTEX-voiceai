"""Readiness: every enabled provider route must have a credential here.

Stage 3 found agents reported "Ready to publish" while a fallback route had
no key, so every live session was refused at bind time. Configuration
validity is environment-independent (validation/); this check is not, so it
runs only where sessions use live providers and only checks presence.
"""

from __future__ import annotations

from typing import Any

from control_plane.agents.models.provider_config import AgentProvidersConfig
from control_plane.agents.validation.rules import ValidationErrorItem
from core.providers.mode import provider_runtime_status

_CATEGORIES = ("stt", "llm", "tts", "s2s")
_LABELS = {
    "stt": "Speech recognition",
    "llm": "Language model",
    "tts": "Voice",
    "s2s": "Speech-to-speech",
}


def _missing(category: str, provider_id: str) -> ValidationErrorItem:
    return ValidationErrorItem(
        "provider_credential_missing",
        f"{_LABELS[category]} provider '{provider_id}' has no API key in this "
        "environment. Add one under Providers or remove it from the chain.",
        field=f"providers.{category}",
    )


async def missing_route_credentials(
    vault: Any, tenant_id: str, providers: AgentProvidersConfig
) -> list[ValidationErrorItem]:
    if provider_runtime_status()["provider_mode"] != "live":
        return []
    issues: list[ValidationErrorItem] = []
    seen: set[tuple[str, str]] = set()
    for category in _CATEGORIES:
        for chain in getattr(providers, category):
            for route in chain.routes:
                if not route.enabled or (category, route.provider_id) in seen:
                    continue
                seen.add((category, route.provider_id))
                present = await vault.has_credential(
                    tenant_id,
                    route.provider_id,
                    credential_ref=route.credential_ref,
                    credential_type="api_key",
                    tier=route.credential_tier,
                )
                if not present:
                    issues.append(_missing(category, route.provider_id))
    return issues
