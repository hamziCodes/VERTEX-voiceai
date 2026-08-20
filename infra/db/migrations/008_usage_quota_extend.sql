-- UCVE Usage Metering & Tenant Quota Extension Migration
-- Migration: 008_usage_quota_extend.sql
-- Description: Extends quota_state with soft/hard caps and sessions with last_heartbeat_at.

ALTER TABLE quota_state
    ADD COLUMN IF NOT EXISTS soft_cap_percent INT NOT NULL DEFAULT 80,
    ADD COLUMN IF NOT EXISTS hard_cap_percent INT NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS max_llm_tokens_month INT NOT NULL DEFAULT 1000000;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
