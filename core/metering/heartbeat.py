"""UCVE Active Session Heartbeat Tracker & Stale Slot Sweeper."""

from __future__ import annotations

import time
from typing import Any


class HeartbeatTracker:
    """Session heartbeat tracker with 2-minute stale session sweeper releasing abandoned slots."""

    def __init__(self, stale_timeout_sec: int = 120) -> None:
        self.stale_timeout_sec = stale_timeout_sec
        self._heartbeats: dict[str, float] = {}

    def update_heartbeat(self, session_id: str) -> None:
        """Update last heartbeat timestamp for session."""
        self._heartbeats[session_id] = time.time()

    def sweep_stale_sessions(self) -> list[str]:
        """Identify and sweep sessions missing heartbeats for longer than stale_timeout_sec (2 min)."""
        now = time.time()
        stale_sessions = []
        for session_id, last_time in list(self._heartbeats.items()):
            if now - last_time > self.stale_timeout_sec:
                stale_sessions.append(session_id)
                del self._heartbeats[session_id]

        return stale_sessions
