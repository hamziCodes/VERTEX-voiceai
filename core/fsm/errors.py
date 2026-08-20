"""UCVE Session FSM Exception Types."""

from __future__ import annotations

from typing import Any


class InvalidStateTransitionError(Exception):
    """Raised when an illegal transition is attempted on the Session FSM."""

    def __init__(self, from_state: Any, event: Any, message: str | None = None) -> None:
        self.from_state = from_state
        self.event = event
        if message is None:
            message = f"Invalid state transition from state '{from_state}' via event '{event}'."
        super().__init__(message)
