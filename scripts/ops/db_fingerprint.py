"""Helpers for the backup/restore drill: migrate, seed, fingerprint, compare."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import psycopg


def _migrate(url: str) -> None:
    from infra.db.migrate import apply_migrations_async

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    applied = asyncio.run(apply_migrations_async(url))
    print(f"migrations applied: {len(applied)}", file=sys.stderr)


def _seed(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as conn:
        for index in range(3):
            tenant = uuid.uuid4()
            conn.execute(
                "INSERT INTO tenants (id, name) VALUES (%s, %s)",
                (tenant, f"Drill tenant {index}"),
            )
            conn.execute(
                "INSERT INTO operational_alerts (alert_key, code, severity, tenant_id, "
                "summary) VALUES (%s, 'QUOTA_SOFT_CAP', 'warning', %s, 'drill')",
                (f"quota_soft_cap:{tenant}:2026-11", tenant),
            )
        conn.execute(
            "INSERT INTO scheduled_job_runs (job_name, slot_start, runner_id, "
            "lease_expires_at) VALUES ('queue_observer', NOW(), 'drill', NOW())"
        )
    print("seeded 3 tenants, 3 alerts, 1 job run", file=sys.stderr)


def _fingerprint(url: str) -> dict:
    with psycopg.connect(url) as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                "ORDER BY tablename"
            ).fetchall()
        ]
        counts = {
            t: conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]  # noqa: S608
            for t in tables
        }
        ledger = conn.execute(
            "SELECT filename, checksum_sha256 FROM schema_migrations ORDER BY filename"
        ).fetchall()
        rls = conn.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relkind = 'r' "
            "ORDER BY relname"
        ).fetchall()
        policies = conn.execute(
            "SELECT tablename, policyname FROM pg_policies ORDER BY 1, 2"
        ).fetchall()
    return {
        "tables": len(tables),
        "row_counts": counts,
        "migrations": [list(r) for r in ledger],
        "rls": [list(r) for r in rls],
        "policies": [list(r) for r in policies],
    }


def _compare(before_path: str, after_path: str) -> None:
    with open(before_path, encoding="utf-8") as f:
        before = json.load(f)
    with open(after_path, encoding="utf-8") as f:
        after = json.load(f)
    problems = [key for key in before if before[key] != after.get(key)]
    rows = sum(before["row_counts"].values())
    print(
        f"tables={before['tables']} rows={rows} migrations={len(before['migrations'])} "
        f"policies={len(before['policies'])}"
    )
    if problems:
        raise SystemExit(f"RESTORE MISMATCH: {problems}")
    print("RESTORE VERIFIED: ledger, row counts, RLS flags and policies identical")


def main() -> None:
    command, *args = sys.argv[1:]
    if command == "migrate":
        _migrate(args[0])
    elif command == "seed":
        _seed(args[0])
    elif command == "fingerprint":
        print(json.dumps(_fingerprint(args[0])))
    elif command == "compare":
        _compare(args[0], args[1])
    else:
        raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main()
