"""Offline contracts for the Phase 07A provider capability catalog."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

import core.providers as providers_package
from core.providers.exceptions import (
    ProviderCapabilityError,
    ProviderFailureCategory,
    UnknownProviderError,
    classify_http_failure,
)
from core.providers.registry import ProviderRegistry
from core.providers.spec import (
    ADVERTISED_PROVIDER_IDS,
    DEFAULT_RELEASE_CHAINS,
    CredentialPolicyState,
    ProviderCatalog,
    ProviderCategory,
    ProviderRolloutState,
    ProviderSpec,
    get_provider_spec,
)


def test_provider_contract_types_are_public_api() -> None:
    assert providers_package.ProviderFailure is not None
    assert providers_package.ProviderFailureCategory is ProviderFailureCategory
    assert providers_package.UnknownProviderError is UnknownProviderError
    assert providers_package.ProviderCapabilityError is ProviderCapabilityError


def test_catalog_covers_every_advertised_provider_with_explicit_state() -> None:
    assert ADVERTISED_PROVIDER_IDS == frozenset(
        {
            "gladia",
            "deepgram",
            "groq",
            "gemini",
            "openai",
            "uplift",
            "elevenlabs",
            "cartesia",
        }
    )
    for provider_id in ADVERTISED_PROVIDER_IDS:
        spec = get_provider_spec(provider_id)
        assert spec.provider_id == provider_id
        assert spec.rollout_state is ProviderRolloutState.OFFLINE_CONTRACT
        assert spec.credential_policy is CredentialPolicyState.BOTH
        assert spec.compliance_tiers == frozenset({"standard"})
        assert {"en", "ur", "ar", "ms"} <= spec.engine_languages


def test_catalog_contracts_match_adapter_shapes() -> None:
    assert get_provider_spec("gladia").category is ProviderCategory.STT
    assert get_provider_spec("gladia").streaming_input is False
    assert get_provider_spec("groq").category is ProviderCategory.LLM
    assert get_provider_spec("groq").streaming_output is True
    assert get_provider_spec("groq").supports_tools is True
    assert get_provider_spec("cartesia").category is ProviderCategory.TTS
    assert get_provider_spec("cartesia").audio_outputs == frozenset({"pcm16"})


def test_provider_spec_is_immutable() -> None:
    spec = get_provider_spec("groq")
    with pytest.raises(FrozenInstanceError):
        spec.provider_id = "changed"  # type: ignore[misc]


def test_catalog_rejects_unknown_category_and_language_mismatches() -> None:
    with pytest.raises(UnknownProviderError, match="unknown"):
        get_provider_spec("unknown")
    with pytest.raises(ProviderCapabilityError, match="category"):
        get_provider_spec("groq", category=ProviderCategory.TTS)

    catalog = ProviderCatalog(
        (
            ProviderSpec(
                provider_id="english-only",
                category=ProviderCategory.STT,
                engine_languages=frozenset({"en"}),
                audio_inputs=frozenset({"pcm16"}),
            ),
        )
    )
    with pytest.raises(ProviderCapabilityError, match="language"):
        catalog.require(
            "english-only",
            category=ProviderCategory.STT,
            language="ur",
        )


def test_registry_validates_every_member_of_a_resilient_chain() -> None:
    assert ProviderRegistry.validate_chain("llm", "ur", ["groq", "gemini"])
    with pytest.raises(UnknownProviderError):
        ProviderRegistry.validate_chain("llm", "ur", ["groq", "unknown"])
    with pytest.raises(ProviderCapabilityError, match="category"):
        ProviderRegistry.validate_chain("llm", "ur", ["groq", "cartesia"])


def test_default_release_chains_match_approved_h07_policy() -> None:
    for language in ("en", "ur", "ar", "ms"):
        assert DEFAULT_RELEASE_CHAINS[language][ProviderCategory.STT] == (
            "gladia",
            "deepgram",
        )
        assert DEFAULT_RELEASE_CHAINS[language][ProviderCategory.LLM] == (
            "groq",
            "gemini",
        )
    assert DEFAULT_RELEASE_CHAINS["ur"][ProviderCategory.TTS] == (
        "uplift",
        "cartesia",
    )
    for language in ("en", "ar", "ms"):
        assert DEFAULT_RELEASE_CHAINS[language][ProviderCategory.TTS] == (
            "cartesia",
            "elevenlabs",
        )


@pytest.mark.parametrize(
    ("status", "category", "retryable"),
    [
        (400, ProviderFailureCategory.INVALID_REQUEST, False),
        (401, ProviderFailureCategory.AUTHENTICATION, False),
        (403, ProviderFailureCategory.AUTHENTICATION, False),
        (408, ProviderFailureCategory.TIMEOUT, True),
        (409, ProviderFailureCategory.INVALID_REQUEST, False),
        (422, ProviderFailureCategory.INVALID_REQUEST, False),
        (429, ProviderFailureCategory.RATE_LIMIT, True),
        (500, ProviderFailureCategory.TRANSIENT_SERVER, True),
        (503, ProviderFailureCategory.TRANSIENT_SERVER, True),
    ],
)
def test_http_failure_classification_is_deterministic(
    status: int,
    category: ProviderFailureCategory,
    retryable: bool,
) -> None:
    failure = classify_http_failure("groq", status)
    assert failure.provider_id == "groq"
    assert failure.status_code == status
    assert failure.category is category
    assert failure.retryable is retryable
