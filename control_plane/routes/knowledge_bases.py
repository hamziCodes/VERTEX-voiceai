"""Authenticated knowledge-base management and truthful lifecycle status."""

from __future__ import annotations

from inspect import isawaitable
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from control_plane.agents.repo import AgentNotFoundError, get_default_agent_config_repo
from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission
from core.db.repos.knowledge_repo import (
    KnowledgeConflictError,
    KnowledgeNotFoundError,
    get_default_knowledge_repository,
    record_to_dict,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
KnowledgeReader = Annotated[AuthContext, Depends(require_permission("knowledge:read"))]
KnowledgeWriter = Annotated[AuthContext, Depends(require_permission("knowledge:write"))]
AgentWriter = Annotated[AuthContext, Depends(require_permission("agent:write"))]


class CreateKnowledgeBaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)


def get_knowledge_repo() -> Any:
    return get_default_knowledge_repository()


def get_agent_repo() -> Any:
    return get_default_agent_config_repo()


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


def _not_found(exc: KnowledgeNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "knowledge_not_found", "message": str(exc)}
    )


def _conflict(exc: KnowledgeConflictError) -> HTTPException:
    return HTTPException(
        status_code=409, detail={"code": exc.code, "message": str(exc)}
    )


@router.get("/status/{tenant_id}")
async def get_kb_status(
    tenant_id: UUID,
    auth: KnowledgeReader,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    """Compatibility aggregate backed by real tenant records and counts."""

    enforce_tenant_access(auth, str(tenant_id))
    return cast(dict[str, Any], await _resolve(repository.aggregate_status(tenant_id)))


@router.post("", status_code=201)
async def create_knowledge_base(
    body: CreateKnowledgeBaseBody,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    try:
        record = await _resolve(
            repository.create_knowledge_base(UUID(auth.tenant_id), body.name)
        )
    except KnowledgeConflictError as exc:
        raise _conflict(exc) from exc
    return record_to_dict(record)


@router.get("")
async def list_knowledge_bases(
    auth: KnowledgeReader,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> list[dict[str, Any]]:
    records = await _resolve(repository.list_knowledge_bases(UUID(auth.tenant_id)))
    return [record_to_dict(record) for record in records]


@router.get("/{knowledge_base_id}")
async def get_knowledge_base(
    knowledge_base_id: UUID,
    auth: KnowledgeReader,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    try:
        record = await _resolve(
            repository.get_knowledge_base(UUID(auth.tenant_id), knowledge_base_id)
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    return record_to_dict(record)


@router.get("/{knowledge_base_id}/sources/{source_id}")
async def get_knowledge_source(
    knowledge_base_id: UUID,
    source_id: UUID,
    auth: KnowledgeReader,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    try:
        source = await _resolve(
            repository.get_source(UUID(auth.tenant_id), knowledge_base_id, source_id)
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    payload = record_to_dict(source)
    payload.pop("object_reference", None)
    return payload


@router.post("/{knowledge_base_id}/sources/{source_id}/retry")
async def retry_knowledge_source(
    knowledge_base_id: UUID,
    source_id: UUID,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    try:
        job = await _resolve(
            repository.retry_source(UUID(auth.tenant_id), knowledge_base_id, source_id)
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeConflictError as exc:
        raise _conflict(exc) from exc
    payload = record_to_dict(job)
    payload["status"] = payload.pop("state")
    return payload


@router.post("/{knowledge_base_id}/activate")
async def activate_knowledge_base(
    knowledge_base_id: UUID,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
) -> dict[str, Any]:
    try:
        record = await _resolve(
            repository.activate_knowledge_base(UUID(auth.tenant_id), knowledge_base_id)
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeConflictError as exc:
        raise _conflict(exc) from exc
    return record_to_dict(record)


@router.post("/{knowledge_base_id}/bind/{agent_id}")
async def bind_knowledge_base(
    knowledge_base_id: UUID,
    agent_id: UUID,
    auth: KnowledgeWriter,
    _agent_auth: AgentWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
    agent_repository: Annotated[Any, Depends(get_agent_repo)],
) -> dict[str, Any]:
    tenant_id = UUID(auth.tenant_id)
    try:
        base = await _resolve(
            repository.get_knowledge_base(tenant_id, knowledge_base_id)
        )
        if base.status.value != "active":
            raise KnowledgeConflictError(
                "knowledge_not_active", "Knowledge base must be active before binding."
            )
        existing = await _resolve(
            repository.find_binding(
                tenant_id, agent_id, knowledge_base_id, base.active_revision
            )
        )
        if existing is not None:
            return record_to_dict(existing)

        draft = await _resolve(agent_repository.get_draft(tenant_id, agent_id))
        references = [
            item
            for item in draft.knowledge_bases
            if str(item.get("id")) != str(knowledge_base_id)
        ]
        references.append(
            {"id": str(knowledge_base_id), "revision": base.active_revision}
        )
        await _resolve(
            agent_repository.save_draft_autosave(
                tenant_id,
                agent_id,
                {"knowledge_bases": references},
                debounce_seconds=0,
                force=True,
            )
        )
        published, _validation = await _resolve(
            agent_repository.publish(
                tenant_id, agent_id, published_by=f"knowledge:{auth.subject_id}"
            )
        )
        binding = await _resolve(
            repository.record_binding(
                tenant_id,
                agent_id,
                published.version,
                knowledge_base_id,
                base.active_revision,
            )
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    except KnowledgeConflictError as exc:
        raise _conflict(exc) from exc
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record_to_dict(binding)
