-- UCVE Core Multi-Tenant Database Schema Migration
-- Migration: 001_core_tenant_schema.sql
-- Description: Creates tenants, agents, sessions, transcripts, recordings, usage, quotas, and compliance profiles.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Key tier enum for platform vs BYOK credentials
CREATE TYPE key_tier_enum AS ENUM ('platform', 'byok');

-- Compliance tier enum for healthcare and privacy requirements
CREATE TYPE compliance_tier_enum AS ENUM ('standard', 'hipaa', 'gdpr_strict');

-- 1. Tenants Table
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    key_tier key_tier_enum NOT NULL DEFAULT 'platform',
    allow_testing_providers BOOLEAN NOT NULL DEFAULT false,
    allowed_origins TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Tenant Compliance Profile Table
CREATE TABLE IF NOT EXISTS tenant_compliance_profile (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    compliance_tier compliance_tier_enum NOT NULL DEFAULT 'standard',
    hipaa_baa_acknowledged_at TIMESTAMPTZ,
    data_retention_days INT NOT NULL DEFAULT 30,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Agents Table
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    system_prompt TEXT NOT NULL DEFAULT '',
    agent_provider_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agents_tenant_id ON agents(tenant_id);

-- 4. Sessions Table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    transport_type VARCHAR(64) NOT NULL DEFAULT 'websocket',
    compliance_tier compliance_tier_enum NOT NULL DEFAULT 'standard',
    config_version_id UUID,
    pinned_at TIMESTAMPTZ,
    degraded_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_sessions_tenant_started ON sessions(tenant_id, started_at DESC);

-- 5. Session Transcripts Table (Queryable JSONB turns split from S3 raw audio)
CREATE TABLE IF NOT EXISTS session_transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    turns JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_transcripts_tenant_session ON session_transcripts(tenant_id, session_id);

-- 6. Session Recordings Table (S3 Pointer + Checksum Metadata)
CREATE TABLE IF NOT EXISTS session_recordings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    s3_uri VARCHAR(1024) NOT NULL,
    checksum_sha256 VARCHAR(64) NOT NULL,
    file_size_bytes BIGINT NOT NULL DEFAULT 0,
    duration_seconds FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_recordings_tenant_session ON session_recordings(tenant_id, session_id);

-- 7. Usage Events Table (Append-only metering logs)
CREATE TABLE IF NOT EXISTS usage_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    usage_kind VARCHAR(64) NOT NULL, -- e.g. 'test_call_sec', 'llm_tokens', 'tts_chars'
    quantity FLOAT NOT NULL DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_at ON usage_events(tenant_id, recorded_at DESC);

-- 8. Quota State Table
CREATE TABLE IF NOT EXISTS quota_state (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    max_concurrent_sessions INT NOT NULL DEFAULT 10,
    monthly_seconds_limit FLOAT NOT NULL DEFAULT 36000.0,
    monthly_seconds_used FLOAT NOT NULL DEFAULT 0.0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
