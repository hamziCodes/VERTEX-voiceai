-- Durable, truthful call lifecycle and incremental transcript state.

ALTER TABLE call_records
    ALTER COLUMN ended_at DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS recording_state VARCHAR(32) NOT NULL DEFAULT 'not_requested',
    ADD COLUMN IF NOT EXISTS recording_error_code VARCHAR(64),
    ADD COLUMN IF NOT EXISTS recording_checksum CHAR(64),
    ADD COLUMN IF NOT EXISTS recording_channel_count SMALLINT,
    ADD COLUMN IF NOT EXISTS recording_duration_seconds DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS recording_storage_region VARCHAR(64),
    ADD COLUMN IF NOT EXISTS policy_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS provider_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS usage_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE call_records
    DROP CONSTRAINT IF EXISTS call_records_recording_state_check;
ALTER TABLE call_records
    ADD CONSTRAINT call_records_recording_state_check CHECK (
        recording_state IN ('not_requested', 'recording', 'available', 'failed')
    );

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM call_records WHERE recording_s3_uri IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'legacy_recording_evidence_requires_resolution';
    END IF;
END
$$;

UPDATE call_records
SET dual_channel = FALSE
WHERE recording_s3_uri IS NULL;

ALTER TABLE call_records
    ALTER COLUMN dual_channel SET DEFAULT FALSE;

ALTER TABLE call_records
    DROP CONSTRAINT IF EXISTS call_records_recording_evidence_check;
ALTER TABLE call_records
    ADD CONSTRAINT call_records_recording_evidence_check CHECK (
        (
            recording_state = 'available'
            AND recording_s3_uri IS NOT NULL
            AND recording_checksum ~ '^[0-9a-f]{64}$'
            AND recording_channel_count IN (1, 2)
            AND recording_duration_seconds > 0
            AND NULLIF(BTRIM(recording_storage_region), '') IS NOT NULL
            AND dual_channel = (recording_channel_count = 2)
            AND recording_error_code IS NULL
        )
        OR
        (
            recording_state <> 'available'
            AND recording_s3_uri IS NULL
            AND recording_checksum IS NULL
            AND recording_channel_count IS NULL
            AND recording_duration_seconds IS NULL
            AND recording_storage_region IS NULL
            AND dual_channel = FALSE
            AND (
                (recording_state = 'failed' AND recording_error_code IS NOT NULL)
                OR
                (recording_state <> 'failed' AND recording_error_code IS NULL)
            )
        )
    );

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM call_records
        WHERE session_id IS NOT NULL
        GROUP BY tenant_id, session_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'legacy_duplicate_call_sessions_require_resolution';
    END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_call_records_tenant_session
    ON call_records (tenant_id, session_id);

ALTER TABLE call_records
    DROP CONSTRAINT IF EXISTS call_records_tenant_session_unique;
ALTER TABLE call_records
    ADD CONSTRAINT call_records_tenant_session_unique
    UNIQUE USING INDEX uq_call_records_tenant_session;

CREATE TABLE IF NOT EXISTS call_record_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id UUID NOT NULL,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    turn_jsonb JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, session_id, ordinal),
    FOREIGN KEY (tenant_id, session_id)
        REFERENCES call_records(tenant_id, session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_call_record_turns_session
    ON call_record_turns (tenant_id, session_id, ordinal);

ALTER TABLE call_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_records FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS call_records_tenant_isolation ON call_records;
CREATE POLICY call_records_tenant_isolation ON call_records FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE call_record_turns ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_record_turns FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS call_record_turns_tenant_isolation ON call_record_turns;
CREATE POLICY call_record_turns_tenant_isolation ON call_record_turns FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON call_records, call_record_turns TO ucve_app;
