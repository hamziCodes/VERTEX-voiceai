"""UCVE Worker CronJob for Automated Daily Data Retention Purge."""

from __future__ import annotations

from core.compliance.retention import RetentionScheduler


def run_purge_job() -> int:
    """Worker entrypoint for scheduled daily retention purge job."""
    scheduler = RetentionScheduler()
    purged_count = scheduler.purge_expired_sessions([])
    return purged_count


if __name__ == "__main__":
    count = run_purge_job()
    print(f"Daily retention purge complete. Purged sessions: {count}")
