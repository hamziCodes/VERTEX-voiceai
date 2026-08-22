"""Tenant Extraction Schema & Field Definitions — Schema cap validation."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ExtractionField(BaseModel):
    """Field definition within a tenant extraction schema."""

    name: str = Field(..., description="Field name identifier, e.g. appointment_date")
    type: str = Field(default="string", description="string / number / boolean / datetime / phone")
    description: str = Field(default="", description="Field extraction prompt context")
    required: bool = Field(default=False)


class TenantExtractionSchema(BaseModel):
    """Tenant-authored extraction schema with max_fields cap enforcement."""

    schema_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(...)
    name: str = Field(default="default_schema")
    fields: list[ExtractionField] = Field(default_factory=list)
    max_fields: int = Field(default=50, description="Per-tenant max field cap (default 50)")

    def validate_schema(self) -> bool:
        """Enforce max_fields cap on schema publish/validation."""
        if len(self.fields) > self.max_fields:
            raise ValueError(f"Extraction schema fields count ({len(self.fields)}) exceeds max_fields ({self.max_fields})")
        return True
