"""Tenant-bound onboarding and entitlement routes for Studio."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from control_plane.agents.templates import list_templates, load_template
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from control_plane.studio.models import OnboardingProfile
from control_plane.studio.repository import StudioRepository, WorkspaceNotFoundError
from core.providers.spec import (
    DEFAULT_PROVIDER_CATALOG,
    DEFAULT_RELEASE_CHAINS,
    ProviderCategory,
)

router = APIRouter(prefix="/v1", tags=["studio"])
OnboardingReader = Annotated[
    AuthContext, Depends(require_permission("onboarding:read"))
]
OnboardingWriter = Annotated[
    AuthContext, Depends(require_permission("onboarding:write"))
]
EntitlementReader = Annotated[
    AuthContext, Depends(require_permission("entitlement:read"))
]
AgentReader = Annotated[AuthContext, Depends(require_permission("agent:read"))]


class OnboardingPatchBody(BaseModel):
    business_name: str | None = Field(default=None, max_length=255)
    use_case: str | None = Field(default=None, max_length=64)
    languages: tuple[str, ...] | None = None
    operating_region: str | None = Field(default=None, max_length=128)
    timezone: str | None = Field(default=None, min_length=1, max_length=128)
    escalation_email: str | None = Field(default=None, max_length=320)
    completed_steps: tuple[str, ...] | None = None


def _repository(request: Request) -> StudioRepository:
    repository = getattr(request.app.state, "studio_repository", None)
    if repository is None:
        raise HTTPException(status_code=503, detail="Studio repository unavailable.")
    return repository


def _tenant_id(auth: AuthContext) -> UUID:
    try:
        return UUID(auth.tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="Invalid tenant identifier."
        ) from exc


def _requirement_codes(profile: OnboardingProfile) -> list[str]:
    requirements = (
        ("business_name_required", profile.business_name),
        ("use_case_required", profile.use_case),
        ("operating_region_required", profile.operating_region),
    )
    return [code for code, value in requirements if not value.strip()]


def _onboarding_response(profile: OnboardingProfile) -> dict[str, Any]:
    return {
        "profile": profile.model_dump(mode="json"),
        "requirement_codes": _requirement_codes(profile),
    }


@router.get("/onboarding")
async def get_onboarding(request: Request, auth: OnboardingReader) -> dict[str, Any]:
    try:
        profile = await _repository(request).get_onboarding(_tenant_id(auth))
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _onboarding_response(profile)


@router.patch("/onboarding")
async def patch_onboarding(
    body: OnboardingPatchBody, request: Request, auth: OnboardingWriter
) -> dict[str, Any]:
    repository = _repository(request)
    tenant_id = _tenant_id(auth)
    try:
        current = await repository.get_onboarding(tenant_id)
        updates = body.model_dump(exclude_unset=True)
        updates = {key: value for key, value in updates.items() if value is not None}
        profile = OnboardingProfile.model_validate(
            {**current.model_dump(), **updates, "tenant_id": tenant_id}
        )
        saved = await repository.save_onboarding(profile)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _onboarding_response(saved)


@router.get("/entitlements")
async def get_entitlements(request: Request, auth: EntitlementReader) -> dict[str, Any]:
    try:
        entitlements = await _repository(request).get_entitlements(_tenant_id(auth))
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return entitlements.model_dump(mode="json")


@router.get("/catalog/providers")
async def get_provider_catalog(
    request: Request,
    auth: AgentReader,
    category: ProviderCategory | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    tenant_id = _tenant_id(auth)
    entitlements = await _repository(request).get_entitlements(tenant_id)
    normalized_language = language.strip().lower() if language else None
    specs = [
        spec
        for provider_category in ProviderCategory
        for spec in DEFAULT_PROVIDER_CATALOG.by_category(provider_category)
        if category is None or spec.category is category
    ]
    if normalized_language:
        specs = [spec for spec in specs if normalized_language in spec.engine_languages]
    if not entitlements.advanced_providers_enabled:
        release_language = normalized_language or "en"
        chain = DEFAULT_RELEASE_CHAINS.get(release_language)
        allowed = {
            provider_id
            for provider_ids in (chain or {}).values()
            for provider_id in provider_ids
        }
        specs = [spec for spec in specs if spec.provider_id in allowed]
    providers = [
        {
            "provider_id": spec.provider_id,
            "category": spec.category.value,
            "languages": sorted(spec.engine_languages),
            "streaming_input": spec.streaming_input,
            "streaming_output": spec.streaming_output,
            "supports_tools": spec.supports_tools,
            "models": list(spec.default_models),
            "readiness": spec.rollout_state.value,
        }
        for spec in sorted(specs, key=lambda item: item.provider_id)
    ]
    return {"providers": providers}


def _safe_template_config(config: dict[str, Any]) -> dict[str, Any]:
    safe = dict(config)
    providers = dict(safe.get("providers") or {})
    known_ids = DEFAULT_PROVIDER_CATALOG.provider_ids
    safe_providers: dict[str, list[dict[str, Any]]] = {}
    for category, groups in providers.items():
        safe_groups: list[dict[str, Any]] = []
        for group in groups:
            safe_group = dict(group)
            safe_group["routes"] = [
                dict(route)
                for route in group.get("routes", [])
                if route.get("provider_id") in known_ids
            ]
            safe_groups.append(safe_group)
        safe_providers[category] = safe_groups
    safe["providers"] = safe_providers
    return safe


@router.get("/agents/templates")
async def get_agent_templates(auth: AgentReader) -> dict[str, Any]:
    del auth
    templates = [
        {
            "template_id": template_id,
            "config": _safe_template_config(load_template(template_id)),
        }
        for template_id in sorted(list_templates())
    ]
    return {"templates": templates}
