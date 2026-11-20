-- Phase 14: durable, de-duplicated operational alerts.
--
-- Alerts are raised by the platform (quota, capacity, provider chains, latency
-- SLO, durable-job dead letters). One row per open alert key; repeats increment
-- ``occurrences`` and ``last_seen_at``. Tenant-scoped rows (tenant_id set) are
-- readable by that tenant through RLS; platform rows (tenant_id NULL) are
-- readable only through platform transactions. Rows never hold transcripts,
-- prompts, phone numbers or credentials: ``summary`` is fixed server text and
-- ``facts`` holds numeric/enum facts only.

CREATE TABLE IF NOT EXISTS operational_alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_key TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    facts JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open',
    occurrences INTEGER NOT NULL DEFAULT 1,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    delivery_status TEXT NOT NULL DEFAULT 'pending',
    delivery_attempted_at TIMESTAMPTZ,
    CONSTRAINT operational_alerts_code_check CHECK (
        code IN (
            'LATENCY_SLO_BREACH',
            'PROVIDER_CHAIN_EXHAUSTED',
            'QUOTA_SOFT_CAP',
            'QUOTA_EXHAUSTED',
            'CAPACITY_EXHAUSTED',
            'JOB_DEAD_LETTER',
            'JOB_RUN_FAILED'
        )
    ),
    CONSTRAINT operational_alerts_severity_check CHECK (
        severity IN ('warning', 'error', 'critical')
    ),
    CONSTRAINT operational_alerts_status_check CHECK (status IN ('open', 'resolved')),
    CONSTRAINT operational_alerts_key_check CHECK (
        char_length(alert_key) BETWEEN 3 AND 200
    ),
    CONSTRAINT operational_alerts_summary_check CHECK (
        char_length(summary) BETWEEN 1 AND 300
    ),
    CONSTRAINT operational_alerts_occurrences_check CHECK (occurrences >= 1),
    CONSTRAINT operational_alerts_delivery_check CHECK (
        delivery_status IN ('pending', 'delivered', 'failed', 'not_configured')
    ),
    CONSTRAINT operational_alerts_resolution_check CHECK (
        (status = 'open' AND resolved_at IS NULL)
        OR (status = 'resolved' AND resolved_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operational_alerts_open_key
    ON operational_alerts (alert_key)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_operational_alerts_recent
    ON operational_alerts (last_seen_at DESC, alert_id);

CREATE INDEX IF NOT EXISTS idx_operational_alerts_tenant
    ON operational_alerts (tenant_id, last_seen_at DESC)
    WHERE tenant_id IS NOT NULL;

ALTER TABLE operational_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE operational_alerts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON operational_alerts FROM ucve_app;
GRANT SELECT ON operational_alerts TO ucve_app;

DROP POLICY IF EXISTS operational_alerts_tenant_read ON operational_alerts;
CREATE POLICY operational_alerts_tenant_read
    ON operational_alerts FOR SELECT TO ucve_app
    USING (
        tenant_id IS NOT NULL
        AND tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
    );
