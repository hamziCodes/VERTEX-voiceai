"""UCVE Agent Builder - Session Configuration Pinning Engine."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.repo import AgentConfigRepo


class SessionConfigPin:
    """Pins sessions to an immutable published agent config version snapshot at call start."""

    def __init__(self, repo: AgentConfigRepo) -> None:
        self.repo = repo
        # Storage for pinned snapshots keyed by session_id
        self._pins: dict[UUID, dict[str, Any]] = {}

    def pin_session(
        self,
        session_id: UUID,
        tenant_id: UUID,
        agent_id: UUID,
        version: int | None = None,
    ) -> AgentConfig:
        """Load published agent configuration and pin it to the session.

        Subsequent calls to get_pinned_config will return this exact snapshot,
        regardless of any subsequent agent edits or publishes.
        """
        config = self.repo.get_published_version(tenant_id, agent_id, version=version)
        snapshot = config.model_dump(mode="json")
        self._pins[session_id] = {
            "pin_id": uuid4(),
            "session_id": session_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "version": config.version,
            "pinned_at": datetime.now(timezone.utc).isoformat(),
            "snapshot": copy.deepcopy(snapshot),
        }
        return config

    def get_pinned_config(self, session_id: UUID) -> AgentConfig | None:
        """Retrieve the pinned configuration for an active session."""
        pin = self._pins.get(session_id)
        if not pin:
            return None
        return AgentConfig.model_validate(pin["snapshot"])

    def unpin_session(self, session_id: UUID) -> None:
        """Release session pin upon call termination."""
        self._pins.pop(session_id, None)
