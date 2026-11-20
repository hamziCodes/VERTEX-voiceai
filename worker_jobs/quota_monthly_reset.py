"""Not a scheduled job: monthly usage needs no reset.

Monthly minutes are computed from the usage ledger with
``date_trunc('month', NOW())`` (``core/db/repos/usage_pg.py``), so a new month
starts at zero without any job. This module never ran anything; Phase 14
classifies it delete-proposed and stops it from printing a fake success.
"""

from __future__ import annotations


def run_monthly_quota_reset() -> int:
    """Return 0: there are no monthly accumulators to reset (see module docs)."""
    reset_count = 0
    return reset_count


if __name__ == "__main__":
    raise SystemExit(
        "quota_monthly_reset is not a job: monthly usage is derived from the ledger."
    )
