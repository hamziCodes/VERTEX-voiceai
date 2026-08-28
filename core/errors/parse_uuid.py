"""Strict UUID parsing — fail-closed identity (no silent uuid4 fallback)."""

from __future__ import annotations

from uuid import UUID

from core.errors.codes import UCVEError, UCVEErrorCode


def parse_uuid(value: str, field: str) -> UUID:
    """Parse a canonical UUID string or raise typed UCVEError."""
    if not value or not isinstance(value, str):
        raise UCVEError(
            UCVEErrorCode.AUTH_INVALID,
            f"Invalid {field}: value is required.",
            details={"field": field},
        )
    try:
        return UUID(value)
    except ValueError as exc:
        raise UCVEError(
            UCVEErrorCode.AUTH_INVALID,
            f"Invalid {field}: must be a valid UUID.",
            details={"field": field, "value_len": len(value)},
        ) from exc
