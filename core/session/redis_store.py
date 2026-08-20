"""UCVE Redis Hot Session State & Turn History Store."""

from __future__ import annotations

import json
import os
from typing import Any

from core.runtime.env import is_test_env


class RedisSessionStore:
    """Hot session state & turn history store supporting Redis and in-memory fallback."""

    def __init__(self, redis_url: str | None = None, session_ttl_sec: int = 3600) -> None:
        url = redis_url if redis_url is not None else os.environ.get("REDIS_URL")
        self._redis_url = url
        self._session_ttl_sec = session_ttl_sec
        self._turns_db: dict[str, list[dict[str, Any]]] = {}
        self._redis = None
        if url and not is_test_env():
            try:
                import redis.asyncio as redis_async

                self._redis = redis_async.from_url(url, decode_responses=True)
            except Exception:
                self._redis = None

    def _key(self, session_id: str) -> str:
        return f"ucve:session:{session_id}:turns"

    async def append_turn(self, session_id: str, turn: dict[str, Any]) -> None:
        """Append turn to hot session turn history."""
        if self._redis is not None:
            key = self._key(session_id)
            await self._redis.rpush(key, json.dumps(turn))
            await self._redis.expire(key, self._session_ttl_sec)
            return
        if self._redis_url and not is_test_env():
            raise RuntimeError("REDIS_URL set but Redis client unavailable.")
        self._turns_db.setdefault(session_id, []).append(turn)

    async def get_turns(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all recorded hot turns for session."""
        if self._redis is not None:
            raw = await self._redis.lrange(self._key(session_id), 0, -1)
            return [json.loads(item) for item in raw]
        return list(self._turns_db.get(session_id, []))

    async def clear_session(self, session_id: str) -> None:
        """Evict session state from hot store on session teardown."""
        if self._redis is not None:
            await self._redis.delete(self._key(session_id))
            return
        self._turns_db.pop(session_id, None)
