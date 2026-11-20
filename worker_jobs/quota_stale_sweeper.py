"""Not a scheduled job: stale admission leases expire inside Redis.

Session admission keeps leases in Redis sorted sets and removes expired
members atomically in its Lua scripts (``core/runtime/admission.py``). This
sweeper built a fresh in-memory tracker and always returned 0. Phase 14
classifies it delete-proposed and stops it from printing a fake success.
"""

from __future__ import annotations

from core.metering.heartbeat import HeartbeatTracker


def run_stale_sweeper() -> int:
    """Worker entrypoint sweeping sessions missing 2-minute heartbeats."""
    tracker = HeartbeatTracker()
    stale_sessions = tracker.sweep_stale_sessions()
    return len(stale_sessions)


if __name__ == "__main__":
    raise SystemExit(
        "quota_stale_sweeper is not a job: Redis admission scripts expire stale leases."
    )
