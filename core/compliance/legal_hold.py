"""UCVE Legal Hold Manager."""

from __future__ import annotations


class LegalHoldManager:
    """Manager for setting and checking legal hold flags blocking session retention purge."""

    def __init__(self) -> None:
        self._holds: set[str] = set()

    def set_legal_hold(self, session_id: str, hold: bool = True) -> None:
        """Apply or release legal hold on session."""
        if hold:
            self._holds.add(session_id)
        else:
            self._holds.discard(session_id)

    def is_legal_hold(self, session_id: str) -> bool:
        """Return True if session is under active legal hold."""
        return session_id in self._holds
