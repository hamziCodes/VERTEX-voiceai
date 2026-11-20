"""Postgres connection helpers for UCVE (H3)."""

from __future__ import annotations

import os
from typing import Any

from core.db.async_pg import DatabaseConfigurationError
from core.runtime.env import is_protected_environment, is_test_env


def database_url() -> str | None:
    return (os.environ.get("DATABASE_URL") or "").strip() or None


def use_memory_repos() -> bool:
    """Allow memory repositories only in test or local development."""
    url = database_url()
    if is_protected_environment():
        if url is None:
            raise DatabaseConfigurationError(
                "Protected environments require durable database repositories."
            )
        return False
    if is_test_env():
        return True
    return url is None


def connect() -> Any:
    import psycopg

    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(url)
