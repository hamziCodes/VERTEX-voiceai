"""Checksum-locked, crash-safe UCVE PostgreSQL migration runner."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATION_NAME = re.compile(r"^(?P<version>\d{3})_[a-z0-9_]+\.sql$")
MIGRATION_LOCK_ID = 8_294_731_991
LEGACY_ALIASES = {
    "017_foundation_hardening.sql": "009_foundation_hardening.sql",
}


class MigrationError(RuntimeError):
    """Base migration runner error."""


class MigrationDriftError(MigrationError):
    """Raised when an applied migration no longer matches source control."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    # Checksums of the same text with CRLF line endings: ledgers written from
    # a Windows checkout before line endings were normalised (Phase 15).
    equivalent_checksums: frozenset[str] = frozenset()

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []
    versions: dict[int, str] = {}
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_NAME.fullmatch(path.name)
        if match is None:
            raise MigrationError(f"Invalid migration filename: {path.name}")
        version = int(match.group("version"))
        if version in versions:
            raise MigrationError(
                f"Duplicate migration version {version:03d}: "
                f"{versions[version]} and {path.name}"
            )
        versions[version] = path.name
        # Hash the text with LF line endings: the same migration must have the
        # same checksum whether the image was built from a Windows (CRLF) or a
        # Linux (LF) checkout, or a deploy refuses to start with "drift".
        content = path.read_bytes().replace(b"\r\n", b"\n")
        crlf = content.replace(b"\n", b"\r\n")
        migrations.append(
            Migration(
                version=version,
                name=path.name,
                path=path,
                checksum=hashlib.sha256(content).hexdigest(),
                equivalent_checksums=frozenset({hashlib.sha256(crlf).hexdigest()}),
            )
        )
    return migrations


def list_migrations() -> list[Path]:
    """Compatibility helper returning validated migration paths."""

    return [migration.path for migration in discover_migrations()]


def validate_applied(migration: Migration, applied_checksum: str | None) -> None:
    if (
        applied_checksum is not None
        and applied_checksum != migration.checksum
        and applied_checksum not in migration.equivalent_checksums
    ):
        raise MigrationDriftError(
            f"Applied migration checksum differs from source: {migration.name}"
        )


async def _execute(connection: Any, sql: str, params: tuple[object, ...] = ()) -> Any:
    return await connection.execute(sql, params)


async def _ensure_schema_migrations(connection: Any) -> None:
    await _execute(
        connection,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            checksum_sha256 CHAR(64),
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
    )
    await _execute(
        connection,
        "ALTER TABLE schema_migrations "
        "ADD COLUMN IF NOT EXISTS checksum_sha256 CHAR(64)",
    )


async def _applied_migrations(connection: Any) -> dict[str, str | None]:
    cursor = await _execute(
        connection,
        "SELECT filename, checksum_sha256 FROM schema_migrations",
    )
    rows = await cursor.fetchall()
    return {str(row[0]): (str(row[1]) if row[1] is not None else None) for row in rows}


async def apply_migrations_async(
    database_url: str | None = None,
    *,
    connection: Any | None = None,
) -> list[str]:
    """Apply each pending migration and its bookkeeping in one transaction."""

    owned_connection = connection is None
    if connection is None:
        import psycopg

        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required to run migrations.")
        connection = await psycopg.AsyncConnection.connect(url, autocommit=True)

    applied_now: list[str] = []
    try:
        async with connection.transaction():
            await _ensure_schema_migrations(connection)
        await _execute(
            connection,
            "SELECT pg_advisory_lock(%s)",
            (MIGRATION_LOCK_ID,),
        )
        try:
            applied = await _applied_migrations(connection)
            for migration in discover_migrations():
                recorded_name = migration.name
                recorded_checksum = applied.get(recorded_name)
                if recorded_name not in applied:
                    legacy_name = LEGACY_ALIASES.get(recorded_name)
                    if legacy_name and legacy_name in applied:
                        recorded_checksum = applied[legacy_name]
                        async with connection.transaction():
                            await _execute(
                                connection,
                                "INSERT INTO schema_migrations "
                                "(filename, checksum_sha256) VALUES (%s, %s) "
                                "ON CONFLICT (filename) DO NOTHING",
                                (migration.name, migration.checksum),
                            )
                        applied[recorded_name] = migration.checksum
                        continue
                if recorded_name in applied:
                    validate_applied(migration, recorded_checksum)
                    if recorded_checksum is None:
                        async with connection.transaction():
                            await _execute(
                                connection,
                                "UPDATE schema_migrations SET checksum_sha256 = %s "
                                "WHERE filename = %s AND checksum_sha256 IS NULL",
                                (migration.checksum, migration.name),
                            )
                    continue
                async with connection.transaction():
                    await _execute(connection, migration.sql)
                    await _execute(
                        connection,
                        "INSERT INTO schema_migrations (filename, checksum_sha256) "
                        "VALUES (%s, %s)",
                        (migration.name, migration.checksum),
                    )
                applied_now.append(migration.name)
                applied[migration.name] = migration.checksum
        finally:
            await _execute(
                connection,
                "SELECT pg_advisory_unlock(%s)",
                (MIGRATION_LOCK_ID,),
            )
    finally:
        if owned_connection:
            await connection.close()
    return applied_now


def apply_migrations(database_url: str | None = None) -> list[str]:
    """Synchronous CLI compatibility wrapper."""

    if sys.platform == "win32":
        # psycopg's async mode cannot run on Windows' default Proactor loop.
        return asyncio.run(
            apply_migrations_async(database_url),
            loop_factory=asyncio.SelectorEventLoop,
        )
    return asyncio.run(apply_migrations_async(database_url))


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
