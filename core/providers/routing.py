"""Tenant-aware construction of immutable, independently callable routes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from core.listening.config import SpeakingPipelineConfig
from core.providers.exceptions import ConfigurationError
from core.providers.factory import (
    build_llm_provider,
    build_stt_provider,
    build_tts_provider,
)
from core.providers.mode import provider_runtime_status
from core.providers.spec import ProviderCategory, get_provider_spec
from core.runtime.session_plan import RuntimeProviderRoute
from core.secrets.exceptions import SecretNotFoundError
from core.secrets.policy import CredentialTier, ResolvedCredential


class CredentialResolver(Protocol):
    def resolve_credential(
        self,
        tenant_id: str,
        provider_id: str,
        *,
        credential_ref: str | None,
        credential_type: str,
        tier: CredentialTier,
    ) -> ResolvedCredential: ...


@dataclass(frozen=True, slots=True)
class ProviderRouteIdentity:
    category: str
    provider_id: str
    model: str | None
    region: str
    tenant_id: str
    credential_scope: str

    @property
    def label(self) -> str:
        return f"{self.category}:{self.provider_id}"

    @property
    def provider_health_key(self) -> tuple[str, str, str, str | None, str]:
        return ("provider", self.category, self.provider_id, self.model, self.region)

    @property
    def credential_health_key(self) -> tuple[str, str, str, str | None, str, str]:
        return (
            "credential",
            self.category,
            self.provider_id,
            self.model,
            self.region,
            self.credential_scope,
        )


@dataclass(frozen=True, slots=True)
class ResolvedProviderRoute:
    identity: ProviderRouteIdentity
    adapter: Any


def _credential_scope(credential: ResolvedCredential) -> str:
    material = "|".join(
        (
            credential.source_tier.value,
            credential.tenant_id,
            credential.provider_id,
            credential.credential_type,
            credential.credential_ref or "platform",
            str(credential.rotation_version),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]


class ProviderRouteBuilder:
    """Validate, resolve, and construct every member of a published chain."""

    def __init__(
        self,
        credential_resolver: CredentialResolver,
        *,
        speaking_config: SpeakingPipelineConfig | None = None,
        stt_mock_text: str = "",
    ) -> None:
        self.credential_resolver = credential_resolver
        self.speaking_config = speaking_config
        self.stt_mock_text = stt_mock_text

    def build_chain(
        self,
        tenant_id: str,
        category: str | ProviderCategory,
        language: str,
        routes: tuple[RuntimeProviderRoute, ...],
    ) -> tuple[ResolvedProviderRoute, ...]:
        normalized_category = ProviderCategory(category)
        ordered = tuple(sorted(routes, key=lambda route: route.priority))
        if len(ordered) < 2:
            raise ConfigurationError(
                f"A production {normalized_category.value} chain requires "
                "at least two routes."
            )

        # Complete capability validation happens before any credential is touched.
        for route in ordered:
            get_provider_spec(
                route.provider_id,
                category=normalized_category,
                language=language,
            )

        built: list[ResolvedProviderRoute] = []
        for route in ordered:
            try:
                credential = self.credential_resolver.resolve_credential(
                    tenant_id,
                    route.provider_id,
                    credential_ref=route.credential_ref,
                    credential_type="api_key",
                    tier=route.credential_tier,
                )
            except SecretNotFoundError:
                if (
                    route.credential_tier is CredentialTier.BYOK
                    or provider_runtime_status()["provider_mode"] != "mock"
                ):
                    raise
                credential = ResolvedCredential(
                    tenant_id=tenant_id,
                    provider_id=route.provider_id,
                    credential_type="api_key",
                    requested_tier=route.credential_tier,
                    source_tier=CredentialTier.PLATFORM,
                    credential_ref=None,
                    rotation_version="explicit-mock",
                    secret="",
                )
            if normalized_category is ProviderCategory.STT:
                adapter = build_stt_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                    mock_text=self.stt_mock_text,
                )
            elif normalized_category is ProviderCategory.LLM:
                adapter = build_llm_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                )
            elif normalized_category is ProviderCategory.TTS:
                adapter = build_tts_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                    speaking_config=self.speaking_config,
                )
            else:
                raise ConfigurationError(
                    "No route factory exists for category "
                    f"{normalized_category.value!r}."
                )
            built.append(
                ResolvedProviderRoute(
                    identity=ProviderRouteIdentity(
                        category=normalized_category.value,
                        provider_id=route.provider_id,
                        model=route.model,
                        region="provider_managed",
                        tenant_id=tenant_id,
                        credential_scope=_credential_scope(credential),
                    ),
                    adapter=adapter,
                )
            )
        return tuple(built)

    async def build_chain_async(
        self,
        tenant_id: str,
        category: str | ProviderCategory,
        language: str,
        routes: tuple[RuntimeProviderRoute, ...],
    ) -> tuple[ResolvedProviderRoute, ...]:
        """Build a chain with an async durable credential resolver when present."""

        resolver = getattr(self.credential_resolver, "aresolve_credential", None)
        if resolver is None:
            return self.build_chain(tenant_id, category, language, routes)
        normalized_category = ProviderCategory(category)
        ordered = tuple(sorted(routes, key=lambda route: route.priority))
        if len(ordered) < 2:
            raise ConfigurationError(
                f"A production {normalized_category.value} chain requires "
                "at least two routes."
            )
        for route in ordered:
            get_provider_spec(
                route.provider_id,
                category=normalized_category,
                language=language,
            )
        built: list[ResolvedProviderRoute] = []
        for route in ordered:
            try:
                credential = await resolver(
                    tenant_id,
                    route.provider_id,
                    credential_ref=route.credential_ref,
                    credential_type="api_key",
                    tier=route.credential_tier,
                )
            except SecretNotFoundError:
                if (
                    route.credential_tier is CredentialTier.BYOK
                    or provider_runtime_status()["provider_mode"] != "mock"
                ):
                    raise
                credential = ResolvedCredential(
                    tenant_id=tenant_id,
                    provider_id=route.provider_id,
                    credential_type="api_key",
                    requested_tier=route.credential_tier,
                    source_tier=CredentialTier.PLATFORM,
                    credential_ref=None,
                    rotation_version="explicit-mock",
                    secret="",
                )
            if normalized_category is ProviderCategory.STT:
                adapter = build_stt_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                    mock_text=self.stt_mock_text,
                )
            elif normalized_category is ProviderCategory.LLM:
                adapter = build_llm_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                )
            else:
                adapter = build_tts_provider(
                    route.provider_id,
                    api_key=credential.secret,
                    model=route.model,
                    speaking_config=self.speaking_config,
                )
            built.append(
                ResolvedProviderRoute(
                    identity=ProviderRouteIdentity(
                        category=normalized_category.value,
                        provider_id=route.provider_id,
                        model=route.model,
                        region="provider_managed",
                        tenant_id=tenant_id,
                        credential_scope=_credential_scope(credential),
                    ),
                    adapter=adapter,
                )
            )
        return tuple(built)
