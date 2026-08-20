"""UCVE Worker CronJob for Sweeping Stale Heartbeat Concurrent Slots."""

from __future__ import annotations

from core.metering.heartbeat import HeartbeatTracker


def run_stale_sweeper() -> int:
    """Worker entrypoint sweeping sessions missing 2-minute heartbeats."""
    tracker = HeartbeatTracker()
    stale_sessions = tracker.sweep_stale_sessions()
    return len(stale_sessions)


if __name__ == "__main__":
    count = run_stale_sweeper()
    print(f"Stale quota sweeper complete. Released slots: {count}")
