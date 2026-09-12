"""Session admission controller for worker concurrency bounds (Phase 31)."""

from __future__ import annotations

import asyncio
from typing import Optional, Set

from core.errors.codes import UCVEErrorCode
from core.runtime.profile_loader import RuntimeProfile, load_profile


class CapacityExceededError(Exception):
    """Raised when worker or cluster is at maximum concurrent session capacity."""

    def __init__(self, message: str = "Worker capacity limit reached"):
        super().__init__(message)
        self.error_code = UCVEErrorCode.QUOTA_EXCEEDED
        self.status_code = 503


class SessionAdmissionController:
    """Controls session admission against the active runtime profile concurrency cap."""

    def __init__(
        self,
        profile: Optional[RuntimeProfile] = None,
        max_sessions: Optional[int] = None,
    ) -> None:
        self.profile = profile or load_profile()
        self.max_sessions = max_sessions if max_sessions is not None else self.profile.max_sessions_per_worker
        self._active_sessions: Set[str] = set()
        self._lock = asyncio.Lock()

    @property
    def active_session_count(self) -> int:
        return len(self._active_sessions)

    def can_admit(self) -> bool:
        """Check if an additional session can be admitted."""
        return len(self._active_sessions) < self.max_sessions

    async def acquire(self, session_id: str) -> bool:
        """Attempt to admit a new session. Raises CapacityExceededError if at capacity."""
        async with self._lock:
            if session_id in self._active_sessions:
                return True
            if len(self._active_sessions) >= self.max_sessions:
                raise CapacityExceededError(
                    f"Active sessions ({len(self._active_sessions)}) reached cap ({self.max_sessions})"
                )
            self._active_sessions.add(session_id)
            return True

    def acquire_sync(self, session_id: str) -> bool:
        """Synchronous admission check for fast non-async callers."""
        if session_id in self._active_sessions:
            return True
        if len(self._active_sessions) >= self.max_sessions:
            raise CapacityExceededError(
                f"Active sessions ({len(self._active_sessions)}) reached cap ({self.max_sessions})"
            )
        self._active_sessions.add(session_id)
        return True

    async def release(self, session_id: str) -> None:
        """Release an admitted session."""
        async with self._lock:
            self._active_sessions.discard(session_id)

    def release_sync(self, session_id: str) -> None:
        """Synchronous release for non-async cleanup."""
        self._active_sessions.discard(session_id)
