"""Verified management identity used by control-plane routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class AuthContext:
    subject_id: str
    tenant_id: str
    roles: tuple[str, ...]
    scopes: frozenset[str]
    auth_method: Literal["api_key", "oidc"]
    key_id: str | None = None

    def __post_init__(self) -> None:
        if not self.subject_id or not self.tenant_id or not self.roles:
            raise ValueError("Authenticated subject, tenant, and role are required.")

    @property
    def primary_role(self) -> str:
        return self.roles[0]

    @property
    def is_platform_admin(self) -> bool:
        return "platform_admin" in self.roles
