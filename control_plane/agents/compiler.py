"""Compile immutable runtime plans from published tenant-scoped agent snapshots."""

from __future__ import annotations

import json
from inspect import isawaitable
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import ValidationError

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.repo import (
    AgentConfigRepo,
    AgentNotFoundError,
    get_default_agent_config_repo,
)
from core.language.registry import LanguageRegistry
from core.providers.exceptions import ConfigurationError
from core.providers.spec import ProviderCategory, get_provider_spec
from core.runtime.session_plan import (
    RuntimeProviderChain,
    RuntimeProviderRoute,
    RuntimeSessionLimits,
    RuntimeSessionPlan,
    RuntimeVoiceBinding,
)
from core.secrets.policy import CredentialTier


class SessionPlanCompilationError(ValueError):
    """Typed failure raised before an invalid published plan reaches a worker."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "password",
        "token",
        "access_token",
        "private_key",
        "credential",
        "credentials",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _assert_no_plaintext_credentials(value: Any, path: str = "config") -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower().replace("-", "_")
            child_path = f"{path}.{raw_key}"
            if key in _SENSITIVE_KEYS:
                raise SessionPlanCompilationError(
                    "PLAINTEXT_CREDENTIAL_FORBIDDEN",
                    f"{child_path} must be replaced by credential_ref",
                )
            _assert_no_plaintext_credentials(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_no_plaintext_credentials(child, f"{path}[{index}]")


def _identifier(value: dict[str, Any], *, kind: str) -> str:
    for key in ("id", f"{kind}_id", "name"):
        candidate = str(value.get(key) or "").strip()
        if candidate:
            return candidate
    raise SessionPlanCompilationError(
        "PUBLISHED_CONFIG_INVALID",
        f"Every {kind} entry requires an id or name.",
    )


def _compile_chains(
    config: AgentConfig,
    languages: tuple[str, ...],
) -> tuple[RuntimeProviderChain, ...]:
    compiled: list[RuntimeProviderChain] = []
    seen: set[tuple[str, str]] = set()
    for category in ("stt", "llm", "tts", "s2s"):
        source_chains = getattr(config.providers, category)
        for chain in source_chains:
            chain_category = chain.category.strip().lower()
            language = chain.language.strip().lower()
            if chain_category != category:
                raise SessionPlanCompilationError(
                    "PROVIDER_CHAIN_CATEGORY_INVALID",
                    f"{category} contains a chain labelled {chain.category!r}",
                )
            if language not in languages:
                raise SessionPlanCompilationError(
                    "PROVIDER_CHAIN_LANGUAGE_INVALID",
                    f"{category}/{language} is outside published languages",
                )
            key = (category, language)
            if key in seen:
                raise SessionPlanCompilationError(
                    "PROVIDER_CHAIN_DUPLICATE",
                    f"Duplicate provider chain for {category}/{language}",
                )
            seen.add(key)
            enabled = sorted(
                (route for route in chain.routes if route.enabled),
                key=lambda route: route.priority,
            )
            priorities = [route.priority for route in enabled]
            if len(priorities) != len(set(priorities)):
                raise SessionPlanCompilationError(
                    "PROVIDER_PRIORITY_DUPLICATE",
                    f"Duplicate route priority for {category}/{language}",
                )
            routes: list[RuntimeProviderRoute] = []
            for route in enabled:
                provider_id = route.provider_id.strip().lower()
                try:
                    get_provider_spec(
                        provider_id,
                        category=ProviderCategory(category),
                        language=language,
                    )
                except (ConfigurationError, ValueError) as exc:
                    raise SessionPlanCompilationError(
                        "PROVIDER_UNSUPPORTED",
                        f"Unsupported {category} provider {provider_id!r}",
                    ) from exc
                credential_ref = (
                    route.credential_ref.strip() if route.credential_ref else None
                )
                credential_tier = CredentialTier(route.credential_tier)
                if (
                    credential_tier in {CredentialTier.BYOK, CredentialTier.BOTH}
                    and credential_ref is None
                ):
                    raise SessionPlanCompilationError(
                        "CREDENTIAL_REFERENCE_REQUIRED",
                        f"{credential_tier.value} route {provider_id!r} requires credential_ref",
                    )
                if (
                    credential_tier is CredentialTier.PLATFORM
                    and credential_ref is not None
                ):
                    raise SessionPlanCompilationError(
                        "PLATFORM_CREDENTIAL_REFERENCE_FORBIDDEN",
                        f"platform route {provider_id!r} must not contain credential_ref",
                    )
                routes.append(
                    RuntimeProviderRoute(
                        provider_id=provider_id,
                        model=(route.model.strip() if route.model else None),
                        priority=route.priority,
                        credential_ref=credential_ref,
                        credential_tier=credential_tier,
                    )
                )
            if not routes:
                raise SessionPlanCompilationError(
                    "PROVIDER_CHAIN_EMPTY",
                    f"No enabled providers for {category}/{language}",
                )
            compiled.append(
                RuntimeProviderChain(
                    category=category,
                    language=language,
                    routes=tuple(routes),
                )
            )

    for category in ("stt", "llm", "tts"):
        for language in languages:
            if (category, language) not in seen:
                raise SessionPlanCompilationError(
                    "PROVIDER_CHAIN_MISSING",
                    f"Missing {category} provider chain for language {language!r}",
                )
    return tuple(sorted(compiled, key=lambda item: (item.category, item.language)))


def _validate_languages(config: AgentConfig) -> tuple[str, ...]:
    languages = tuple(
        dict.fromkeys(language.strip().lower() for language in config.languages)
    )
    if not languages or any(not language for language in languages):
        raise SessionPlanCompilationError(
            "LANGUAGE_POLICY_INVALID", "At least one language is required."
        )
    registry = LanguageRegistry.load_defaults()
    unsupported = [
        language for language in languages if registry.get_profile(language) is None
    ]
    if unsupported:
        raise SessionPlanCompilationError(
            "LANGUAGE_UNSUPPORTED",
            f"Unsupported published languages: {unsupported}",
        )
    return languages


def _compile_published(config: AgentConfig) -> RuntimeSessionPlan:
    if not config.is_published or config.published_at is None:
        raise SessionPlanCompilationError(
            "PUBLISHED_CONFIG_REQUIRED", "Agent version is not published."
        )
    raw = config.model_dump(mode="json")
    _assert_no_plaintext_credentials(raw)
    languages = _validate_languages(config)
    chains = _compile_chains(config, languages)

    extra_voice_languages = set(config.persona.voice_by_language) - set(languages)
    if extra_voice_languages:
        raise SessionPlanCompilationError(
            "VOICE_MAPPING_INVALID",
            "Voice mappings reference unpublished languages: "
            f"{sorted(extra_voice_languages)}",
        )
    voices = tuple(
        RuntimeVoiceBinding(
            language=language,
            voice_id=(
                config.persona.voice_by_language.get(language)
                or config.persona.voice_id
            ).strip(),
        )
        for language in languages
    )
    if any(not binding.voice_id for binding in voices):
        raise SessionPlanCompilationError(
            "VOICE_MAPPING_INVALID", "Every published language requires a voice."
        )

    tool_allowlist = tuple(
        dict.fromkeys(_identifier(tool, kind="tool") for tool in config.tools)
    )
    knowledge_base_ids = tuple(
        dict.fromkeys(
            _identifier(knowledge_base, kind="knowledge_base")
            for knowledge_base in config.knowledge_bases
        )
    )
    try:
        limits = RuntimeSessionLimits.model_validate(config.session_limits)
    except ValidationError as exc:
        raise SessionPlanCompilationError("SESSION_LIMITS_INVALID", str(exc)) from exc

    credential_references = tuple(
        sorted(
            {
                route.credential_ref
                for chain in chains
                for route in chain.routes
                if route.credential_ref
            }
        )
    )
    compliance_tier = str(config.compliance.get("tier") or "standard").strip()
    plan_id = str(
        uuid5(
            NAMESPACE_URL,
            f"wavia:session-plan:{config.tenant_id}:{config.agent_id}:{config.version}",
        )
    )
    return RuntimeSessionPlan.create(
        plan_id=plan_id,
        tenant_id=str(config.tenant_id),
        agent_id=str(config.agent_id),
        agent_version=config.version,
        system_prompt=config.persona.system_prompt.strip(),
        initial_greeting=(
            config.persona.greeting.strip() if config.persona.greeting else None
        ),
        allowed_languages=languages,
        default_language=languages[0],
        voices=voices,
        provider_chains=chains,
        credential_references=credential_references,
        tool_allowlist=tool_allowlist,
        tool_definitions_json=_canonical_json(config.tools),
        knowledge_base_ids=knowledge_base_ids,
        extraction_schema_id=config.extraction_schema_id,
        extraction_schema_json=(
            _canonical_json(config.extraction_schema)
            if config.extraction_schema is not None
            else None
        ),
        telephony_policy_json=(
            _canonical_json(config.telephony) if config.telephony is not None else None
        ),
        compliance_tier=compliance_tier,
        hipaa_baa_acknowledged=bool(
            config.compliance.get("hipaa_baa_acknowledged", False)
        ),
        limits=limits,
    )


def compile_agent_version(
    tenant_id: UUID | str,
    agent_id: UUID | str,
    version: int | None,
    *,
    repo: AgentConfigRepo | None = None,
) -> RuntimeSessionPlan:
    """Compile one tenant-scoped immutable published snapshot into a runtime plan."""

    source = repo or get_default_agent_config_repo()
    try:
        tenant_uuid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
        agent_uuid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))
        config = source.get_published_version(
            tenant_uuid,
            agent_uuid,
            version=version,
        )
    except (AgentNotFoundError, TypeError, ValueError) as exc:
        if isinstance(exc, SessionPlanCompilationError):
            raise
        raise SessionPlanCompilationError(
            "PUBLISHED_CONFIG_NOT_FOUND",
            "Published agent version was not found for this tenant.",
        ) from exc
    try:
        source.validator.validate(config).raise_if_invalid()
    except ValueError as exc:
        raise SessionPlanCompilationError("PUBLISHED_CONFIG_INVALID", str(exc)) from exc
    return _compile_published(config)


async def compile_agent_version_async(
    tenant_id: UUID | str,
    agent_id: UUID | str,
    version: int | None,
    *,
    repo: Any | None = None,
) -> RuntimeSessionPlan:
    """Compile a published snapshot from either async durable or memory storage."""

    source = repo or get_default_agent_config_repo()
    try:
        tenant_uuid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
        agent_uuid = agent_id if isinstance(agent_id, UUID) else UUID(str(agent_id))
        loaded = source.get_published_version(
            tenant_uuid,
            agent_uuid,
            version=version,
        )
        config = await loaded if isawaitable(loaded) else loaded
    except (AgentNotFoundError, TypeError, ValueError) as exc:
        raise SessionPlanCompilationError(
            "PUBLISHED_CONFIG_NOT_FOUND",
            "Published agent version was not found for this tenant.",
        ) from exc
    try:
        source.validator.validate(config).raise_if_invalid()
    except ValueError as exc:
        raise SessionPlanCompilationError("PUBLISHED_CONFIG_INVALID", str(exc)) from exc
    return _compile_published(config)


def build_unsafe_demo_plan(
    tenant_id: str,
    agent_id: str,
    *,
    system_prompt: str = "",
) -> RuntimeSessionPlan:
    """Build a visibly unsafe local-only compatibility plan for unpublished demos."""

    prompt = system_prompt.strip() or (
        "You are Wavia Voice AI, a concise local development assistant."
    )
    return RuntimeSessionPlan.create(
        plan_id=str(uuid5(NAMESPACE_URL, f"wavia:unsafe-demo:{tenant_id}:{agent_id}")),
        tenant_id=tenant_id,
        agent_id=agent_id,
        agent_version=1,
        system_prompt=prompt,
        allowed_languages=("en",),
        default_language="en",
        voices=(RuntimeVoiceBinding(language="en", voice_id="default"),),
        provider_chains=(
            RuntimeProviderChain(
                category="stt",
                language="en",
                routes=(RuntimeProviderRoute(provider_id="gladia", priority=1),),
            ),
            RuntimeProviderChain(
                category="llm",
                language="en",
                routes=(
                    RuntimeProviderRoute(
                        provider_id="groq",
                        model="openai/gpt-oss-120b",
                        priority=1,
                    ),
                ),
            ),
            RuntimeProviderChain(
                category="tts",
                language="en",
                routes=(RuntimeProviderRoute(provider_id="uplift", priority=1),),
            ),
        ),
        unsafe_demo=True,
    )
