"""UCVE Agent Builder HTTP API Routes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from control_plane.agents import (
    AgentConfig,
    AgentConfigRepo,
    AgentNotFoundError,
    SessionConfigPin,
)
from control_plane.agents.repo import get_default_agent_config_repo
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission

router = APIRouter(prefix="/v1/agents", tags=["agents"])
AgentReader = Annotated[AuthContext, Depends(require_permission("agent:read"))]
AgentWriter = Annotated[AuthContext, Depends(require_permission("agent:write"))]

# Module-level default repository and pin engine instance
_agent_repo = get_default_agent_config_repo()
_pin_engine = SessionConfigPin(_agent_repo)


def get_agent_repo() -> AgentConfigRepo:
    return _agent_repo


def get_pin_engine() -> SessionConfigPin:
    return _pin_engine


class CreateAgentBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="")
    persona: dict[str, Any] | None = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    providers: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None


class AutosavePatchBody(BaseModel):
    patch: dict[str, Any]
    debounce_seconds: float = 30.0
    force: bool = False


class PinSessionBody(BaseModel):
    session_id: UUID
    version: int | None = None


@router.post("", status_code=201)
async def create_agent(
    body: CreateAgentBody,
    auth: AgentWriter,
) -> dict[str, Any]:
    """Create a new agent draft under the tenant."""
    tenant_uuid = UUID(auth.tenant_id)
    config_dict: dict[str, Any] = {
        "tenant_id": tenant_uuid,
        "name": body.name,
        "description": body.description,
        "languages": body.languages,
    }
    if body.persona:
        config_dict["persona"] = body.persona
    if body.providers:
        config_dict["providers"] = body.providers
    if body.compliance:
        config_dict["compliance"] = body.compliance

    config = AgentConfig.model_validate(config_dict)
    saved = _agent_repo.create_agent(config)
    return saved.model_dump(mode="json")


@router.get("")
async def list_agents(
    auth: AgentReader,
) -> list[dict[str, Any]]:
    """List all agents for the tenant."""
    tenant_uuid = UUID(auth.tenant_id)
    agents = _agent_repo.list_agents(tenant_uuid)
    return [a.model_dump(mode="json") for a in agents]


@router.get("/{agent_id}")
async def get_agent_draft(
    agent_id: UUID,
    auth: AgentReader,
) -> dict[str, Any]:
    """Retrieve the editable draft of an agent."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        draft = _agent_repo.get_draft(tenant_uuid, agent_id)
        return draft.model_dump(mode="json")
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{agent_id}/autosave")
async def autosave_draft(
    agent_id: UUID,
    body: AutosavePatchBody,
    auth: AgentWriter,
) -> dict[str, Any]:
    """Apply debounced updates to the agent draft."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        config, did_save = _agent_repo.save_draft_autosave(
            tenant_uuid,
            agent_id,
            body.patch,
            debounce_seconds=body.debounce_seconds,
            force=body.force,
        )
        return {
            "saved": did_save,
            "agent": config.model_dump(mode="json"),
        }
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{agent_id}/publish")
async def publish_agent(
    agent_id: UUID,
    auth: AgentWriter,
) -> dict[str, Any]:
    """Validate and publish an agent draft into an immutable version snapshot."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        published, val_res = _agent_repo.publish(
            tenant_uuid, agent_id, published_by=auth.subject_id
        )
        return {
            "version": published.version,
            "published_at": published.published_at.isoformat()
            if published.published_at
            else None,
            "config": published.model_dump(mode="json"),
        }
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{agent_id}/versions")
async def list_agent_versions(
    agent_id: UUID,
    auth: AgentReader,
) -> list[dict[str, Any]]:
    """List published version metadata."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        return _agent_repo.list_versions(tenant_uuid, agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{agent_id}/versions/{version}")
async def get_agent_version_snapshot(
    agent_id: UUID,
    version: int,
    auth: AgentReader,
) -> dict[str, Any]:
    """Get an immutable published snapshot by version."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        cfg = _agent_repo.get_published_version(tenant_uuid, agent_id, version=version)
        return cfg.model_dump(mode="json")
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{agent_id}/pin")
async def pin_session_config(
    agent_id: UUID,
    body: PinSessionBody,
    auth: AgentWriter,
) -> dict[str, Any]:
    """Pin an active session to a published agent version snapshot."""
    tenant_uuid = UUID(auth.tenant_id)
    try:
        pinned = _pin_engine.pin_session(
            body.session_id, tenant_uuid, agent_id, version=body.version
        )
        return {
            "session_id": str(body.session_id),
            "agent_id": str(agent_id),
            "version": pinned.version,
            "pinned": True,
        }
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
