"""Immutable, hash-addressed runtime configuration for one published agent version."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.secrets.policy import CredentialTier

SESSION_PLAN_SCHEMA_VERSION = "1.1.0"


class SessionPlanIntegrityError(ValueError):
    """Raised when a serialized runtime plan is malformed or hash-invalid."""


class RuntimeProviderRoute(BaseModel):
    """One immutable provider route containing a reference, never a credential."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_id: str = Field(min_length=1)
    model: str | None = None
    priority: int = Field(ge=1)
    credential_ref: str | None = None
    credential_tier: CredentialTier = CredentialTier.PLATFORM


class RuntimeProviderChain(BaseModel):
    """Ordered provider routes for a category and language."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: Literal["stt", "llm", "tts", "s2s"]
    language: str = Field(min_length=2)
    routes: tuple[RuntimeProviderRoute, ...] = Field(min_length=1)


class RuntimeVoiceBinding(BaseModel):
    """Published language-to-voice binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str = Field(min_length=2)
    voice_id: str = Field(min_length=1)


class RuntimeSessionLimits(BaseModel):
    """Published limits enforced for a session using this plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_duration_sec: int = Field(default=3600, ge=1, le=86400)
    max_turns: int = Field(default=500, ge=1, le=10000)


class RuntimeSessionSelection(BaseModel):
    """A caller choice constrained by the published plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    language: str
    voice_id: str


class RuntimeSessionPlan(BaseModel):
    """Complete immutable runtime contract compiled from a published snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = SESSION_PLAN_SCHEMA_VERSION
    plan_id: str = Field(min_length=1)
    plan_hash: str = ""
    tenant_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_version: int = Field(ge=1)
    system_prompt: str = Field(min_length=1)
    initial_greeting: str | None = None
    allowed_languages: tuple[str, ...] = Field(min_length=1)
    default_language: str = Field(min_length=2)
    voices: tuple[RuntimeVoiceBinding, ...] = Field(min_length=1)
    provider_chains: tuple[RuntimeProviderChain, ...] = Field(min_length=1)
    credential_references: tuple[str, ...] = ()
    tool_allowlist: tuple[str, ...] = ()
    tool_definitions_json: str = "[]"
    knowledge_base_ids: tuple[str, ...] = ()
    extraction_schema_id: str | None = None
    extraction_schema_json: str | None = None
    telephony_policy_json: str | None = None
    compliance_tier: str = "standard"
    hipaa_baa_acknowledged: bool = False
    limits: RuntimeSessionLimits = Field(default_factory=RuntimeSessionLimits)
    unsafe_demo: bool = False

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def hash_payload(self) -> dict[str, Any]:
        """Return the complete serialized plan except its self-referential hash."""

        return self.model_dump(mode="json", exclude={"plan_hash"})

    def computed_hash(self) -> str:
        canonical = self._canonical_json(self.hash_payload()).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def create(cls, **values: Any) -> RuntimeSessionPlan:
        """Build a plan and seal it with its canonical SHA-256 digest."""

        provisional = cls(**values, plan_hash="")
        return provisional.model_copy(update={"plan_hash": provisional.computed_hash()})

    def verify_hash(self) -> None:
        if not self.plan_hash or self.plan_hash != self.computed_hash():
            raise SessionPlanIntegrityError("Runtime session plan hash is invalid.")

    def to_snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible snapshot."""

        return self.model_dump(mode="json")

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> RuntimeSessionPlan:
        """Validate, reconstruct, and authenticate a serialized snapshot."""

        try:
            plan = cls.model_validate(snapshot)
        except ValidationError as exc:
            raise SessionPlanIntegrityError(
                "Runtime session plan snapshot is invalid."
            ) from exc
        plan.verify_hash()
        return plan

    def provider_chain(self, category: str, language: str) -> RuntimeProviderChain:
        normalized = language.strip().lower()
        for chain in self.provider_chains:
            if chain.category == category and chain.language == normalized:
                return chain
        raise ValueError(
            f"No published {category} provider chain for language {normalized!r}."
        )

    def primary_route(self, category: str, language: str) -> RuntimeProviderRoute:
        return self.provider_chain(category, language).routes[0]

    def voice_for_language(self, language: str) -> str:
        normalized = language.strip().lower()
        for binding in self.voices:
            if binding.language == normalized:
                return binding.voice_id
        raise ValueError(f"No published voice for language {normalized!r}.")

    def select(
        self,
        *,
        language: str | None = None,
        voice_id: str | None = None,
    ) -> RuntimeSessionSelection:
        """Resolve only caller choices explicitly allowed by this plan."""

        chosen_language = (language or self.default_language).strip().lower()
        if chosen_language not in self.allowed_languages:
            raise ValueError(
                f"language {chosen_language!r} is not allowed by published plan"
            )
        published_voice = self.voice_for_language(chosen_language)
        chosen_voice = (voice_id or published_voice).strip()
        if chosen_voice != published_voice:
            raise ValueError(
                f"voice {chosen_voice!r} is not allowed for language "
                f"{chosen_language!r} by published plan"
            )
        return RuntimeSessionSelection(
            language=chosen_language,
            voice_id=chosen_voice,
        )
