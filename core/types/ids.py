"""UCVE Branded Identifier Types & Validation."""

from __future__ import annotations

from typing import NewType
import uuid

SessionId = NewType("SessionId", str)
CallId = NewType("CallId", str)
TenantId = NewType("TenantId", str)


def validate_uuid_string(val: str) -> str:
    """Validate that val is a valid string representation of a UUID."""
    try:
        val_uuid = uuid.UUID(val)
        return str(val_uuid)
    except ValueError as exc:
        raise ValueError(f"Invalid UUID string format: {val}") from exc


def generate_session_id() -> SessionId:
    """Generate a new canonical SessionId (UUID v4 string)."""
    return SessionId(str(uuid.uuid4()))


def generate_call_id() -> CallId:
    """Generate a new canonical CallId (UUID v4 string)."""
    return CallId(str(uuid.uuid4()))


def generate_tenant_id() -> TenantId:
    """Generate a new canonical TenantId (UUID v4 string)."""
    return TenantId(str(uuid.uuid4()))
