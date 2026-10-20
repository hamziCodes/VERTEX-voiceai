"""Source-controlled provider capability and rollout contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from core.providers.exceptions import ProviderCapabilityError, UnknownProviderError


class ProviderCategory(StrEnum):
    STT = "stt"
    LLM = "llm"
    TTS = "tts"
    S2S = "s2s"


class CredentialPolicyState(StrEnum):
    """Business policy chosen in H07; unresolved is deliberate, not a default."""

    UNRESOLVED = "unresolved"
    PLATFORM = "platform"
    BYOK = "byok"
    BOTH = "both"


class ProviderRolloutState(StrEnum):
    """Evidence level for a provider adapter in this repository."""

    OFFLINE_CONTRACT = "offline_contract"
    LIVE_QUALIFIED = "live_qualified"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Immutable capabilities known from the checked-in adapter contract."""

    provider_id: str
    category: ProviderCategory
    engine_languages: frozenset[str]
    streaming_input: bool = False
    streaming_output: bool = False
    supports_tools: bool = False
    audio_inputs: frozenset[str] = frozenset()
    audio_outputs: frozenset[str] = frozenset()
    default_models: tuple[str, ...] = ()
    regions: frozenset[str] = frozenset({"provider_managed"})
    compliance_tiers: frozenset[str] = frozenset({"standard"})
    credential_policy: CredentialPolicyState = CredentialPolicyState.UNRESOLVED
    rollout_state: ProviderRolloutState = ProviderRolloutState.OFFLINE_CONTRACT

    def __post_init__(self) -> None:
        normalized_id = self.provider_id.strip().lower()
        if not normalized_id or normalized_id != self.provider_id:
            raise ValueError("provider_id must be a non-empty lowercase identifier")
        if not self.engine_languages:
            raise ValueError("engine_languages must not be empty")


class ProviderCatalog:
    """Immutable lookup table for provider specifications."""

    def __init__(self, specs: tuple[ProviderSpec, ...]) -> None:
        values: dict[str, ProviderSpec] = {}
        for spec in specs:
            if spec.provider_id in values:
                raise ValueError(f"Duplicate provider ID: {spec.provider_id}")
            values[spec.provider_id] = spec
        self._specs: Mapping[str, ProviderSpec] = MappingProxyType(values)

    @property
    def provider_ids(self) -> frozenset[str]:
        return frozenset(self._specs)

    def by_category(self, category: ProviderCategory) -> tuple[ProviderSpec, ...]:
        return tuple(spec for spec in self._specs.values() if spec.category is category)

    def require(
        self,
        provider_id: str,
        *,
        category: ProviderCategory | None = None,
        language: str | None = None,
    ) -> ProviderSpec:
        normalized = provider_id.strip().lower()
        spec = self._specs.get(normalized)
        if spec is None:
            raise UnknownProviderError(f"Unknown provider ID: {provider_id!r}")
        if category is not None and spec.category is not category:
            raise ProviderCapabilityError(
                f"Provider {normalized!r} category is {spec.category.value!r}, "
                f"not {category.value!r}."
            )
        if language is not None:
            normalized_language = language.strip().lower()
            if normalized_language not in spec.engine_languages:
                raise ProviderCapabilityError(
                    f"Provider {normalized!r} is not configured for language "
                    f"{normalized_language!r}."
                )
        return spec


_ENGINE_LANGUAGES = frozenset({"en", "ur", "ar", "ms"})

DEFAULT_PROVIDER_CATALOG = ProviderCatalog(
    (
        ProviderSpec(
            provider_id="gladia",
            category=ProviderCategory.STT,
            engine_languages=_ENGINE_LANGUAGES,
            audio_inputs=frozenset({"pcm16"}),
        ),
        ProviderSpec(
            provider_id="deepgram",
            category=ProviderCategory.STT,
            engine_languages=_ENGINE_LANGUAGES,
            audio_inputs=frozenset({"pcm16"}),
            default_models=("nova-3",),
        ),
        ProviderSpec(
            provider_id="groq",
            category=ProviderCategory.LLM,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            supports_tools=True,
            default_models=("openai/gpt-oss-120b",),
        ),
        ProviderSpec(
            provider_id="gemini",
            category=ProviderCategory.LLM,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            supports_tools=True,
            default_models=("gemini-2.5-flash",),
        ),
        ProviderSpec(
            provider_id="openai",
            category=ProviderCategory.LLM,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            supports_tools=True,
            default_models=("gpt-4o-mini",),
        ),
        ProviderSpec(
            provider_id="uplift",
            category=ProviderCategory.TTS,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            audio_outputs=frozenset({"pcm16"}),
        ),
        ProviderSpec(
            provider_id="elevenlabs",
            category=ProviderCategory.TTS,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            audio_outputs=frozenset({"pcm16"}),
            default_models=("eleven_multilingual_v2",),
        ),
        ProviderSpec(
            provider_id="cartesia",
            category=ProviderCategory.TTS,
            engine_languages=_ENGINE_LANGUAGES,
            streaming_output=True,
            audio_outputs=frozenset({"pcm16"}),
            default_models=("sonic-2",),
        ),
    )
)

ADVERTISED_PROVIDER_IDS = DEFAULT_PROVIDER_CATALOG.provider_ids


def get_provider_spec(
    provider_id: str,
    *,
    category: ProviderCategory | None = None,
    language: str | None = None,
) -> ProviderSpec:
    """Resolve and validate one advertised provider contract."""

    return DEFAULT_PROVIDER_CATALOG.require(
        provider_id,
        category=category,
        language=language,
    )
