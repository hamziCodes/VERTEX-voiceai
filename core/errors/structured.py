"""Structured Error Model & HTTP Status Code Mapping."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from core.errors.codes import UCVEErrorCode

ERROR_CODE_HTTP_STATUS_MAP: dict[UCVEErrorCode, int] = {
    UCVEErrorCode.AUTH_INVALID: 401,
    UCVEErrorCode.AUTH_EXPIRED: 401,
    UCVEErrorCode.QUOTA_EXCEEDED: 429,
    UCVEErrorCode.PROVIDER_TIMEOUT: 504,
    UCVEErrorCode.PROVIDER_UNAVAILABLE: 503,
    UCVEErrorCode.FSM_INVALID_TRANSITION: 400,
    UCVEErrorCode.HIPAA_BAA_REQUIRED: 403,
    UCVEErrorCode.WEBHOOK_SIGNATURE_INVALID: 401,
    UCVEErrorCode.TRUNK_UNAVAILABLE: 503,
    UCVEErrorCode.EXTRACTION_FAILED: 500,
    UCVEErrorCode.DISPATCH_FAILED: 500,
    UCVEErrorCode.INTERNAL_ERROR: 500,
}


class StructuredError(BaseModel):
    """Structured operational error model."""

    code: UCVEErrorCode
    message: str
    severity: str = Field(default="error", description="info / warn / error / critical")
    correlation_id: UUID = Field(default_factory=uuid4)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    def to_http_status(self) -> int:
        """Map error code to standard HTTP status code."""
        return ERROR_CODE_HTTP_STATUS_MAP.get(self.code, 500)
