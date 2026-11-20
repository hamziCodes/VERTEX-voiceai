"""Control Plane Extraction Schemas API Router Stub."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission
from post_call.extraction.schema import TenantExtractionSchema

router = APIRouter(prefix="/extraction-schemas", tags=["extraction"])
ExtractionWriter = Annotated[
    AuthContext, Depends(require_permission("extraction:write"))
]


@router.post("")
async def create_extraction_schema(
    schema: TenantExtractionSchema,
    auth: ExtractionWriter,
) -> dict[str, Any]:
    """Create or update a tenant extraction schema with max_fields validation."""
    enforce_tenant_access(auth, str(schema.tenant_id))
    try:
        schema.validate_schema()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "created",
        "schema_id": schema.schema_id,
        "tenant_id": schema.tenant_id,
        "fields_count": len(schema.fields),
    }
