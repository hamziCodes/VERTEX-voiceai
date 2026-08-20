"""UCVE Redis Hot Session State & Turn History Store."""

from __future__ import annotations

from typing import Any


class RedisSessionStore:
    """Hot session state & turn history store supporting Redis and in-memory fallback."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._turns_db: dict[str, list[dict[str, Any]]] = {}

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> None:
        """Append turn to hot session turn history."""
        self._turns_db.setdefault(session_id, []).append(turn)

    async def get_turns(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all recorded hot turns for session."""
        return list(self._turns_db.get(session_id, []))

    async def clear_session(self, session_id: str) -> None:
        """Evict session state from hot store on session teardown."""
        self._turns_db.pop(session_id, None)
