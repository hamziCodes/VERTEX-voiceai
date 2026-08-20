"""Apply UCVE SQL migrations in order (001–009+)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def list_migrations() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def ensure_schema_migrations(conn) -> None:  # type: ignore[no-untyped-def]
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def applied_filenames(conn) -> set[str]:  # type: ignore[no-untyped-def]
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {r[0] for r in rows}


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Apply pending migrations. Returns list of newly applied filenames."""
    import psycopg

    url = database_url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required to run migrations.")

    applied: list[str] = []
    with psycopg.connect(url, autocommit=True) as conn:
        ensure_schema_migrations(conn)
        done = applied_filenames(conn)
        for path in list_migrations():
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)",
                (path.name,),
            )
            applied.append(path.name)
    return applied


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UCVE DB migrate")
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    try:
        applied = apply_migrations(args.database_url)
    except Exception as exc:
        print(f"MIGRATION FAILED: {exc}", file=sys.stderr)
        return 1
    if applied:
        print("Applied:", ", ".join(applied))
    else:
        print("OK: no pending migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
