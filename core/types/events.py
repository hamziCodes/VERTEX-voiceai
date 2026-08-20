"""UCVE Canonical Control Events & Wire Serialization."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any


class ControlEventType(str, Enum):
    """Canonical control event types across transports."""

    BARGE_IN = "barge_in"
    FLUSH = "flush"
    HANGUP = "hangup"
    LANGUAGE_CHANGED = "language_changed"
    METRIC = "metric"
    DEGRADED_MODE = "degraded_mode"
    PONG = "pong"
    PLAYBACK_STARTED = "playback_started"


@dataclass(frozen=True)
class ControlEvent:
    """Immutable control event container for real-time signaling."""

    event_type: ControlEventType
    timestamp_ms: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Serialize event to JSON wire string."""
        data = {
            "event_type": self.event_type.value if isinstance(self.event_type, Enum) else self.event_type,
            "timestamp_ms": self.timestamp_ms,
            "payload": self.payload,
        }
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> ControlEvent:
        """Deserialize event from JSON wire string."""
        data = json.loads(json_str)
        event_type = ControlEventType(data["event_type"])
        return cls(
            event_type=event_type,
            timestamp_ms=float(data.get("timestamp_ms", 0.0)),
            payload=dict(data.get("payload", {})),
        )
