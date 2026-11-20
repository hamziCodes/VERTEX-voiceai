"""Encrypted provider-credential lifecycle routes with redacted DTOs."""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, SecretStr, field_validator

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import require_permission
from core.providers.exceptions import UnknownProviderError
from core.providers.spec import DEFAULT_PROVIDER_CATALOG
from core.secrets.repository import CredentialRecord

router = APIRouter(prefix="/v1/provider-credentials", tags=["provider-credentials"])
CredentialReader = Annotated[
    AuthContext, Depends(require_permission("provider_credential:read"))
]
CredentialWriter = Annotated[
    AuthContext, Depends(require_permission("provider_credential:write"))
]
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")


class CreateProviderCredentialBody(BaseModel):
    provider_id: str = Field(min_length=1, max_length=128)
    credential_type: str = Field(default="api_key", min_length=1, max_length=64)
    reference: str = Field(default="default", min_length=1, max_length=128)
    secret: SecretStr

    @field_validator("provider_id", "credential_type", "reference")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized = value.strip().lower()
        if _SAFE_NAME.fullmatch(normalized) is None:
            raise ValueError("identifier contains unsupported characters")
        return normalized


def _credential_id(record: CredentialRecord) -> str:
    identity = (
        f"{record.tenant_id}\0{record.provider_id}\0"
        f"{record.credential_type}\0{record.credential_ref}"
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def _safe_metadata(record: CredentialRecord) -> dict[str, Any]:
    return {
        "credential_id": _credential_id(record),
        "provider_id": record.provider_id,
        "credential_type": record.credential_type,
        "reference": record.credential_ref,
        "rotation_version": record.rotation_version,
        "status": "active",
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "rotated_at": record.rotated_at.isoformat() if record.rotated_at else None,
    }


def _vault(request: Request):  # type: ignore[no-untyped-def]
    vault = getattr(request.app.state, "secret_vault", None)
    if vault is None:
        raise HTTPException(status_code=503, detail="Credential vault unavailable.")
    return vault


@router.get("")
async def list_provider_credentials(
    request: Request, auth: CredentialReader
) -> dict[str, Any]:
    records = await _vault(request).alist_records(auth.tenant_id)
    return {"credentials": [_safe_metadata(record) for record in records]}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_provider_credential(
    body: CreateProviderCredentialBody,
    request: Request,
    auth: CredentialWriter,
) -> dict[str, Any]:
    try:
        DEFAULT_PROVIDER_CATALOG.require(body.provider_id)
    except UnknownProviderError as exc:
        raise HTTPException(status_code=422, detail="Unknown provider.") from exc
    secret = body.secret.get_secret_value()
    if not secret:
        raise HTTPException(status_code=422, detail="Credential value is required.")
    record = await _vault(request).astore(
        auth.tenant_id,
        body.provider_id,
        secret,
        credential_type=body.credential_type,
        credential_ref=body.reference,
    )
    return _safe_metadata(record)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_provider_credential(
    credential_id: str,
    request: Request,
    auth: CredentialWriter,
) -> Response:
    if re.fullmatch(r"[0-9a-f]{64}", credential_id) is None:
        raise HTTPException(status_code=404, detail="Credential not found.")
    vault = _vault(request)
    records = await vault.alist_records(auth.tenant_id)
    record = next(
        (item for item in records if _credential_id(item) == credential_id), None
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Credential not found.")
    removed = await vault.arevoke(
        auth.tenant_id,
        record.provider_id,
        record.credential_type,
        credential_ref=record.credential_ref,
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Credential not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
