"""Tenant Extraction Schema & Field Definitions — Schema cap validation."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractionField(BaseModel):
    """Field definition within a tenant extraction schema."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$", description="Field name"
    )
    type: Literal["string", "number", "boolean", "datetime", "phone"] = "string"
    description: str = Field(default="", description="Field extraction prompt context")
    required: bool = Field(default=False)
    sensitive: bool = Field(default=False)
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class TenantExtractionSchema(BaseModel):
    """Tenant-authored extraction schema with max_fields cap enforcement."""

    model_config = ConfigDict(extra="forbid")

    schema_id: UUID = Field(default_factory=uuid4)
    tenant_id: UUID = Field(...)
    name: str = Field(default="default_schema")
    fields: list[ExtractionField] = Field(default_factory=list)
    max_fields: int = Field(
        default=50, description="Per-tenant max field cap (default 50)"
    )

    @field_validator("fields")
    @classmethod
    def unique_field_names(cls, fields: list[ExtractionField]) -> list[ExtractionField]:
        names = [field.name for field in fields]
        if len(set(names)) != len(names):
            raise ValueError("Extraction field names must be unique.")
        return fields

    def validate_schema(self) -> bool:
        """Enforce max_fields cap on schema publish/validation."""
        if len(self.fields) > self.max_fields:
            raise ValueError(
                "Extraction schema fields count "
                f"({len(self.fields)}) exceeds max_fields ({self.max_fields})"
            )
        return True
