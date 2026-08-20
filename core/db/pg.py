"""Postgres connection helpers for UCVE (H3)."""

from __future__ import annotations

import os
from typing import Any

from core.runtime.env import is_test_env


def database_url() -> str | None:
    return (os.environ.get("DATABASE_URL") or "").strip() or None


def use_memory_repos() -> bool:
    """In-memory repos for UCVE_ENV=test or when DATABASE_URL unset."""
    if is_test_env():
        return True
    return database_url() is None


def connect() -> Any:
    import psycopg

    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set.")
    return psycopg.connect(url)
