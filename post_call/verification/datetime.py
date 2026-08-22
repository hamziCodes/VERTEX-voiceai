"""Timezone-aware Date & Time Verification Helper."""

from __future__ import annotations

from datetime import datetime, timezone


def parse_and_verify_datetime(dt_str: str | None, clinic_timezone: str = "UTC") -> datetime | None:
    """Parse date string into timezone-aware datetime. Return None if unparseable/invalid."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
