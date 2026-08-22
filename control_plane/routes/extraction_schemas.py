"""Control Plane Extraction Schemas API Router Stub."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException

from post_call.extraction.schema import ExtractionField, TenantExtractionSchema

router = APIRouter(prefix="/extraction-schemas", tags=["extraction"])


@router.post("")
async def create_extraction_schema(schema: TenantExtractionSchema) -> dict[str, Any]:
    """Create or update a tenant extraction schema with max_fields validation."""
    try:
        schema.validate_schema()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "status": "created",
        "schema_id": schema.schema_id,
        "tenant_id": schema.tenant_id,
        "fields_count": len(schema.fields),
    }
