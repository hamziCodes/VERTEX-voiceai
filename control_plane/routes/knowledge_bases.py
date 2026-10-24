"""Authenticated knowledge-base management and truthful lifecycle status."""

from __future__ import annotations

from inspect import isawaitable
from pathlib import PurePath
from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
from core.rag.ingestion.parsers.base import IngestionParseError
from core.rag.ingestion.parsers.faq import parse_faq
from core.rag.ingestion.validation import IngestionValidationError, validate_upload
from core.storage.knowledge_objects import (
    KnowledgeObjectStore,
    get_default_knowledge_object_store,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
KnowledgeReader = Annotated[AuthContext, Depends(require_permission("knowledge:read"))]
KnowledgeWriter = Annotated[AuthContext, Depends(require_permission("knowledge:write"))]
AgentWriter = Annotated[AuthContext, Depends(require_permission("agent:write"))]


class CreateKnowledgeBaseBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class FAQItemBody(BaseModel):
    question: str = Field(min_length=1, max_length=2_000)
    answer: str = Field(min_length=1, max_length=20_000)


class CreateFAQSourceBody(BaseModel):
    name: str = Field(default="FAQ", min_length=1, max_length=255)
    items: list[FAQItemBody] = Field(min_length=1, max_length=1_000)


def get_knowledge_repo() -> Any:
    return get_default_knowledge_repository()


def get_agent_repo() -> Any:
    return get_default_agent_config_repo()


def get_knowledge_object_store() -> KnowledgeObjectStore:
    return get_default_knowledge_object_store()


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


async def _create_source(
    *,
    tenant_id: UUID,
    knowledge_base_id: UUID,
    display_name: str,
    media_type: str,
    content: bytes,
    repository: Any,
    object_store: KnowledgeObjectStore,
) -> dict[str, Any]:
    validated = validate_upload(display_name, media_type, content)
    reference = await object_store.put(
        tenant_id, content, suffix=PurePath(validated.display_name).suffix
    )
    try:
        source = await _resolve(
            repository.create_source(
                tenant_id,
                knowledge_base_id,
                source_type=validated.source_type,
                display_name=validated.display_name,
                media_type=validated.media_type,
                byte_count=validated.byte_count,
                checksum_sha256=validated.checksum_sha256,
                object_reference=reference,
            )
        )
    except Exception:
        await object_store.delete(reference)
        raise
    if source.object_reference != reference:
        await object_store.delete(reference)
    payload = record_to_dict(source)
    payload.pop("object_reference", None)
    return payload


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


@router.post("/{knowledge_base_id}/sources", status_code=202)
async def upload_knowledge_source(
    knowledge_base_id: UUID,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
    object_store: Annotated[KnowledgeObjectStore, Depends(get_knowledge_object_store)],
    source: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    content = bytearray()
    while chunk := await source.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "file_too_large",
                    "message": "File exceeds the upload limit.",
                },
            )
    try:
        return await _create_source(
            tenant_id=UUID(auth.tenant_id),
            knowledge_base_id=knowledge_base_id,
            display_name=source.filename or "upload",
            media_type=source.content_type or "application/octet-stream",
            content=bytes(content),
            repository=repository,
            object_store=object_store,
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    except IngestionValidationError as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.post("/{knowledge_base_id}/faqs", status_code=202)
async def create_faq_source(
    knowledge_base_id: UUID,
    body: CreateFAQSourceBody,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
    object_store: Annotated[KnowledgeObjectStore, Depends(get_knowledge_object_store)],
) -> dict[str, Any]:
    import json

    content = json.dumps(
        [item.model_dump() for item in body.items], ensure_ascii=False
    ).encode()
    try:
        parse_faq(content)
        return await _create_source(
            tenant_id=UUID(auth.tenant_id),
            knowledge_base_id=knowledge_base_id,
            display_name=f"{body.name}.json",
            media_type="application/json",
            content=content,
            repository=repository,
            object_store=object_store,
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc
    except (IngestionValidationError, IngestionParseError) as exc:
        raise HTTPException(
            status_code=422, detail={"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.delete("/{knowledge_base_id}/sources/{source_id}", status_code=204)
async def delete_knowledge_source(
    knowledge_base_id: UUID,
    source_id: UUID,
    auth: KnowledgeWriter,
    repository: Annotated[Any, Depends(get_knowledge_repo)],
    object_store: Annotated[KnowledgeObjectStore, Depends(get_knowledge_object_store)],
) -> None:
    try:
        tenant_id = UUID(auth.tenant_id)
        source = await _resolve(
            repository.get_source(tenant_id, knowledge_base_id, source_id)
        )
        await object_store.delete(source.object_reference)
        await _resolve(
            repository.delete_source(tenant_id, knowledge_base_id, source_id)
        )
    except KnowledgeNotFoundError as exc:
        raise _not_found(exc) from exc


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
