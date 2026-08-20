"""UCVE Worker CronJob for Automated Daily Data Retention Purge."""

from __future__ import annotations

import datetime
import os
from typing import Any

from core.compliance.retention import RetentionScheduler
from core.db.pg import database_url, use_memory_repos


# Process-local fixture store for tests / jobs without Postgres
_FIXTURE_SESSIONS: list[dict[str, Any]] = []


def seed_fixture_session(session: dict[str, Any]) -> None:
    _FIXTURE_SESSIONS.append(session)


def clear_fixture_sessions() -> None:
    _FIXTURE_SESSIONS.clear()


def _load_expired_sessions() -> tuple[list[dict[str, Any]], Any]:
    """Load expired sessions from Postgres or in-memory fixtures."""
    if use_memory_repos() or not database_url():
        now = datetime.datetime.now(datetime.timezone.utc)
        expired = [
            s
            for s in list(_FIXTURE_SESSIONS)
            if s.get("purge_after")
            and s["purge_after"] <= now
            and not s.get("legal_hold")
        ]
        return expired, None

    import psycopg

    conn = psycopg.connect(database_url())  # type: ignore[arg-type]
    rows = conn.execute(
        """
        SELECT id::text AS session_id, legal_hold, purge_after
        FROM sessions
        WHERE legal_hold = false
          AND purge_after IS NOT NULL
          AND purge_after <= NOW()
        """
    ).fetchall()
    expired = [
        {"session_id": r[0], "legal_hold": r[1], "purge_after": r[2]} for r in rows
    ]
    return expired, conn


def run_purge_job() -> int:
    """Worker entrypoint for scheduled daily retention purge job."""
    scheduler = RetentionScheduler()
    expired, conn = _load_expired_sessions()

    def _delete(session_id: str) -> None:
        if conn is not None:
            conn.execute("DELETE FROM sessions WHERE id = %s::uuid", (session_id,))
        else:
            _FIXTURE_SESSIONS[:] = [
                s
                for s in _FIXTURE_SESSIONS
                if (s.get("session_id") or s.get("id")) != session_id
            ]

    try:
        purged_count = scheduler.purge_expired_sessions(
            expired, delete_session=_delete
        )
        if conn is not None:
            conn.commit()
        return purged_count
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    count = run_purge_job()
    print(f"Daily retention purge complete. Purged sessions: {count}")
