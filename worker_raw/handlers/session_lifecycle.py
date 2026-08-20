"""UCVE Worker Session Lifecycle Handler."""

from __future__ import annotations

from typing import Any

from worker_raw.orchestration.pipeline import PipelineOrchestrator
from worker_raw.orchestration.session_config import PipelineSessionConfig


class SessionLifecycleHandler:
    """Manages session connect, disconnect, heartbeat, and basic reconnect events."""

    def __init__(self) -> None:
        self._active_sessions: dict[str, PipelineOrchestrator] = {}

    async def handle_connect(self, config: PipelineSessionConfig) -> PipelineOrchestrator:
        """Handle client connect event, spinning up new PipelineOrchestrator instance."""
        orchestrator = PipelineOrchestrator()
        self._active_sessions[config.session_id] = orchestrator
        return orchestrator

    async def handle_disconnect(self, session_id: str) -> None:
        """Handle client disconnect event, cleaning up active session."""
        self._active_sessions.pop(session_id, None)
