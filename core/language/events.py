"""UCVE Language Changed Event Model."""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from typing import Any


@dataclass
class LanguageChangedEvent:
    """Event emitted when real-time LanguageRouter switches active conversation language."""

    session_id: str
    tenant_id: str
    language_from: str
    language_to: str
    reason: str = "stt_detection"
    timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "language_from": self.language_from,
            "language_to": self.language_to,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }
