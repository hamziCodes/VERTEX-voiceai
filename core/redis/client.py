"""One way to build Redis clients, with bounded timeouts and stale-link checks.

``health_check_interval`` makes redis-py PING a pooled connection that has
been idle for that long before reusing it. After a Redis restart the first
command otherwise goes out on a dead socket and fails (the Phase 15
Redis-restart drill: the first mint after a restart was refused). A PING is
safe to retry; replaying a ``SET NX`` would not be, so commands themselves
are not retried here.
"""

from __future__ import annotations

from typing import Any

HEALTH_CHECK_INTERVAL_S = 5
SOCKET_TIMEOUT_S = 2.0


def _options(decode_responses: bool) -> dict[str, Any]:
    return {
        "decode_responses": decode_responses,
        "health_check_interval": HEALTH_CHECK_INTERVAL_S,
        "socket_connect_timeout": SOCKET_TIMEOUT_S,
        "socket_timeout": SOCKET_TIMEOUT_S,
    }


def async_redis_from_url(url: str, *, decode_responses: bool = True) -> Any:
    import redis.asyncio as redis_async

    return redis_async.from_url(url, **_options(decode_responses))


def sync_redis_from_url(url: str, *, decode_responses: bool = True) -> Any:
    import redis

    return redis.from_url(url, **_options(decode_responses))
