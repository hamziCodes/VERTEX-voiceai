"""Tenant API-key lifecycle routes with one-time plaintext delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from inspect import isawaitable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission

router = APIRouter(prefix="/v1/api-keys", tags=["api-keys"])
APIKeyReader = Annotated[AuthContext, Depends(require_permission("api_key:read"))]
APIKeyWriter = Annotated[AuthContext, Depends(require_permission("api_key:write"))]


class CreateAPIKeyBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: tuple[str, ...] = ("session:mint",)
    role: str = "tenant_viewer"
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(
            sorted(set(value.strip() for value in values if value.strip()))
        )
        if not normalized or len(normalized) > 50:
            raise ValueError("between 1 and 50 scopes are required")
        if any(len(value) > 128 or ":" not in value for value in normalized):
            raise ValueError("scopes must use bounded resource:action names")
        return normalized

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"tenant_viewer", "tenant_editor"}:
            raise ValueError("API keys may use tenant_viewer or tenant_editor roles")
        return normalized


async def _resolve(value: Any) -> Any:
    return await value if isawaitable(value) else value


def _safe_key(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key_id": str(record["key_id"]),
        "name": str(record["name"]),
        "key_prefix": str(record["key_prefix"]),
        "scopes": list(record.get("scopes") or ()),
        "role": str(record["role"]),
        "created_at": record["created_at"].isoformat()
        if record.get("created_at")
        else None,
        "expires_at": record["expires_at"].isoformat()
        if record.get("expires_at")
        else None,
        "revoked_at": record["revoked_at"].isoformat()
        if record.get("revoked_at")
        else None,
        "last_used_at": record["last_used_at"].isoformat()
        if record.get("last_used_at")
        else None,
    }


@router.get("")
async def list_api_keys(request: Request, auth: APIKeyReader) -> dict[str, Any]:
    records = await _resolve(request.app.state.api_keys.list_api_keys(auth.tenant_id))
    return {"keys": [_safe_key(record) for record in records]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateAPIKeyBody, request: Request, auth: APIKeyWriter
) -> dict[str, Any]:
    if body.expires_at is not None and body.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="Expiry must be in the future.")
    studio_repository = request.app.state.studio_repository
    entitlements = await studio_repository.get_entitlements(UUID(auth.tenant_id))
    records = await _resolve(request.app.state.api_keys.list_api_keys(auth.tenant_id))
    now = datetime.now(UTC)
    active_count = sum(
        record.get("revoked_at") is None
        and (record.get("expires_at") is None or record["expires_at"] > now)
        for record in records
    )
    if active_count >= entitlements.api_keys_allowed:
        raise HTTPException(status_code=409, detail="API key quota reached.")
    plaintext, key_id = await _resolve(
        request.app.state.api_keys.generate_api_key(
            auth.tenant_id,
            body.name,
            scopes=list(body.scopes),
            role=body.role,
            created_by=auth.subject_id,
            expires_at=body.expires_at,
        )
    )
    updated = await _resolve(request.app.state.api_keys.list_api_keys(auth.tenant_id))
    metadata = next(record for record in updated if str(record["key_id"]) == key_id)
    return {"api_key": plaintext, "key": _safe_key(metadata)}


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID, request: Request, auth: APIKeyWriter
) -> Response:
    try:
        await _resolve(
            request.app.state.api_keys.revoke_api_key(auth.tenant_id, str(key_id))
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="API key not found.") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
