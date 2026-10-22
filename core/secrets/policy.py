"""Typed credential policy and secret-safe resolution metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class CredentialTier(StrEnum):
    """Published source policy for one provider route."""

    PLATFORM = "platform"
    BYOK = "byok"
    BOTH = "both"


@dataclass(frozen=True, slots=True)
class ResolvedCredential:
    """One in-memory credential result whose secret cannot appear in repr."""

    tenant_id: str
    provider_id: str
    credential_type: str
    requested_tier: CredentialTier
    source_tier: CredentialTier
    credential_ref: str | None
    rotation_version: int | str
    secret: str = field(repr=False, compare=False)
