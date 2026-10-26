from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "infra" / "db" / "migrations" / "024_post_call_runtime.sql"


def test_phase11_migration_declares_durable_call_and_turn_contract() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    for fragment in (
        "alter table call_records",
        "recording_state",
        "recording_checksum",
        "recording_channel_count",
        "recording_duration_seconds",
        "recording_storage_region",
        "policy_snapshot",
        "provider_snapshot",
        "usage_snapshot",
        "create table if not exists call_record_turns",
        "unique (tenant_id, session_id, ordinal)",
        "force row level security",
        "with check",
        "legacy_duplicate_call_sessions_require_resolution",
        "legacy_recording_evidence_requires_resolution",
        "call_records_recording_evidence_check",
    ):
        assert fragment in sql
