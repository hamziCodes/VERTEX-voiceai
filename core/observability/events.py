"""UCVE Metric Wire Event Serialization."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class MetricEvent:
    """Wire metric event for transport / WebSocket emission."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "metric",
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp_ms": self.timestamp_ms,
        }
