"""UCVE Turn Context Data Structure."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnContext:
    """Stateful context for a voice conversation session and turn tracking."""

    session_id: str
    current_language: str = "en"
    turn_index: int = 0
    degraded_flags: dict[str, Any] = field(default_factory=dict)
