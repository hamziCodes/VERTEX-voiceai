"""Alert vocabulary. Codes and severities are closed sets (mirrored in SQL)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class AlertCode(StrEnum):
    LATENCY_SLO_BREACH = "LATENCY_SLO_BREACH"
    PROVIDER_CHAIN_EXHAUSTED = "PROVIDER_CHAIN_EXHAUSTED"
    QUOTA_SOFT_CAP = "QUOTA_SOFT_CAP"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    CAPACITY_EXHAUSTED = "CAPACITY_EXHAUSTED"
    JOB_DEAD_LETTER = "JOB_DEAD_LETTER"
    JOB_RUN_FAILED = "JOB_RUN_FAILED"


class AlertSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


SEVERITY_RANK = {
    AlertSeverity.WARNING: 1,
    AlertSeverity.ERROR: 2,
    AlertSeverity.CRITICAL: 3,
}

# Facts are numbers, booleans or short enum-like strings. Anything else is
# dropped so an alert can never carry conversation content or identifiers.
_MAX_FACTS = 12
_MAX_FACT_STRING = 64


def sanitize_facts(facts: dict[str, Any] | None) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in (facts or {}).items():
        if len(clean) >= _MAX_FACTS:
            break
        if isinstance(value, bool | int | float):
            clean[str(key)[:48]] = value
        elif (
            isinstance(value, str)
            and len(value) <= _MAX_FACT_STRING
            and value.replace("_", "")
            .replace("-", "")
            .replace(".", "")
            .replace(":", "")
            .isalnum()
        ):
            clean[str(key)[:48]] = value
    return clean


@dataclass(frozen=True)
class Alert:
    alert_id: UUID
    alert_key: str
    code: AlertCode
    severity: AlertSeverity
    tenant_id: UUID | None
    summary: str
    facts: dict[str, Any]
    status: str
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    delivery_status: str = "pending"

    def to_public(self) -> dict[str, Any]:
        return {
            "alert_id": str(self.alert_id),
            "code": self.code.value,
            "severity": self.severity.value,
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "summary": self.summary,
            "facts": dict(self.facts),
            "status": self.status,
            "occurrences": self.occurrences,
            "first_seen_at": self.first_seen_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "delivery_status": self.delivery_status,
        }


@dataclass(frozen=True)
class RaisedAlert:
    """Outcome of raising an alert: ``is_new`` drives notification."""

    alert: Alert
    is_new: bool
    escalated: bool = False
    delivery: str = field(default="not_attempted")
