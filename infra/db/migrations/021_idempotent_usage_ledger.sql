-- Idempotent provider-correlated usage ledger.

ALTER TABLE usage_events
    ADD COLUMN IF NOT EXISTS event_key VARCHAR(255),
    ADD COLUMN IF NOT EXISTS unit VARCHAR(32) NOT NULL DEFAULT 'units',
    ADD COLUMN IF NOT EXISTS provider_id VARCHAR(128),
    ADD COLUMN IF NOT EXISTS provider_request_id VARCHAR(255),
    ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

UPDATE usage_events SET event_key = id::text WHERE event_key IS NULL;
ALTER TABLE usage_events ALTER COLUMN event_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS usage_events_tenant_event_key_uq
    ON usage_events (tenant_id, event_key);

CREATE INDEX IF NOT EXISTS usage_events_tenant_kind_month_idx
    ON usage_events (tenant_id, usage_kind, recorded_at DESC);

ALTER TABLE usage_events
    DROP CONSTRAINT IF EXISTS usage_events_quantity_nonnegative;
ALTER TABLE usage_events
    ADD CONSTRAINT usage_events_quantity_nonnegative CHECK (quantity >= 0) NOT VALID;
