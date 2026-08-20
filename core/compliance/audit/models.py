"""UCVE Audit Event Model Entity."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
import uuid
from typing import Any

from core.compliance.audit.actions import AuditAction


@dataclass
class AuditEvent:
    """Immutable audit log event entity."""

    tenant_id: str
    action: str | AuditAction
    resource_type: str
    resource_id: str
    actor_id: str = "system"
    actor_type: str = "system"
    detail: dict[str, Any] = field(default_factory=dict)
    ip: str | None = None
    user_agent: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        action_val = self.action.value if isinstance(self.action, AuditAction) else self.action
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type,
            "action": action_val,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "detail": self.detail,
            "ip": self.ip,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
        }
