-- Durable tenant-scoped knowledge workflow and local embedding profile.

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'draft',
    active_revision INTEGER NOT NULL DEFAULT 0 CHECK (active_revision >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_base_status_check CHECK (
        status IN ('draft', 'processing', 'ready', 'active', 'failed', 'deleting')
    ),
    UNIQUE (tenant_id, id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_bases_tenant_name_ci
    ON knowledge_bases (tenant_id, lower(name));

CREATE TABLE IF NOT EXISTS knowledge_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    media_type VARCHAR(127) NOT NULL,
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    checksum_sha256 CHAR(64) NOT NULL,
    object_reference TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    parser_version VARCHAR(64),
    language_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    error_code VARCHAR(64),
    error_message VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_source_status_check CHECK (
        status IN (
            'uploaded', 'queued', 'parsing', 'chunking', 'embedding',
            'ready', 'failed', 'deleting'
        )
    ),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, knowledge_base_id, checksum_sha256, revision),
    FOREIGN KEY (tenant_id, knowledge_base_id)
        REFERENCES knowledge_bases(tenant_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS knowledge_ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL,
    source_id UUID NOT NULL,
    state VARCHAR(32) NOT NULL DEFAULT 'queued',
    attempt INTEGER NOT NULL DEFAULT 1 CHECK (attempt > 0),
    lease_owner VARCHAR(255),
    lease_expires_at TIMESTAMPTZ,
    retry_at TIMESTAMPTZ,
    progress_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key VARCHAR(255) NOT NULL,
    last_error_code VARCHAR(64),
    last_error_message VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT knowledge_job_state_check CHECK (
        state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    UNIQUE (tenant_id, idempotency_key),
    UNIQUE (tenant_id, source_id),
    FOREIGN KEY (tenant_id, knowledge_base_id)
        REFERENCES knowledge_bases(tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, source_id)
        REFERENCES knowledge_sources(tenant_id, id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_agent_configs_tenant_agent'
    ) THEN
        ALTER TABLE agent_configs ADD CONSTRAINT uq_agent_configs_tenant_agent
            UNIQUE (tenant_id, agent_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_agent_versions_tenant_version'
    ) THEN
        ALTER TABLE agent_config_versions
            ADD CONSTRAINT uq_agent_versions_tenant_version
            UNIQUE (tenant_id, version_id);
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS agent_knowledge_bindings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL,
    agent_version_id UUID NOT NULL,
    agent_config_version INTEGER NOT NULL CHECK (agent_config_version > 0),
    knowledge_base_id UUID NOT NULL,
    knowledge_revision INTEGER NOT NULL CHECK (knowledge_revision > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, agent_version_id, knowledge_base_id),
    UNIQUE (tenant_id, agent_id, knowledge_base_id, knowledge_revision),
    FOREIGN KEY (tenant_id, agent_id)
        REFERENCES agent_configs(tenant_id, agent_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, agent_version_id)
        REFERENCES agent_config_versions(tenant_id, version_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, knowledge_base_id)
        REFERENCES knowledge_bases(tenant_id, id) ON DELETE CASCADE
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM knowledge_chunks LIMIT 1) THEN
        RAISE EXCEPTION 'legacy_knowledge_chunks_require_reingestion';
    END IF;
END
$$;

DROP INDEX IF EXISTS idx_knowledge_chunks_embedding;
ALTER TABLE knowledge_chunks
    ALTER COLUMN embedding TYPE vector(384),
    ADD COLUMN IF NOT EXISTS knowledge_base_id UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS knowledge_source_id UUID REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS revision INTEGER,
    ADD COLUMN IF NOT EXISTS ordinal INTEGER,
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255),
    ADD COLUMN IF NOT EXISTS embedding_version VARCHAR(64),
    ADD COLUMN IF NOT EXISTS token_count INTEGER,
    ADD COLUMN IF NOT EXISTS citation_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS content_hash CHAR(64);

ALTER TABLE knowledge_chunks
    ADD CONSTRAINT knowledge_chunks_base_tenant_fk
        FOREIGN KEY (tenant_id, knowledge_base_id)
        REFERENCES knowledge_bases(tenant_id, id) ON DELETE CASCADE,
    ADD CONSTRAINT knowledge_chunks_source_tenant_fk
        FOREIGN KEY (tenant_id, knowledge_source_id)
        REFERENCES knowledge_sources(tenant_id, id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_knowledge_bases_tenant
    ON knowledge_bases (tenant_id, created_at);
CREATE INDEX IF NOT EXISTS idx_knowledge_sources_revision
    ON knowledge_sources (tenant_id, knowledge_base_id, revision, status);
CREATE INDEX IF NOT EXISTS idx_knowledge_jobs_claim
    ON knowledge_ingestion_jobs (state, retry_at, lease_expires_at, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_lookup
    ON agent_knowledge_bindings (tenant_id, agent_id, knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_scope
    ON knowledge_chunks (tenant_id, knowledge_base_id, revision);
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

ALTER TABLE knowledge_bases ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_bases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS knowledge_bases_tenant_isolation ON knowledge_bases;
CREATE POLICY knowledge_bases_tenant_isolation ON knowledge_bases FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE knowledge_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_sources FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS knowledge_sources_tenant_isolation ON knowledge_sources;
CREATE POLICY knowledge_sources_tenant_isolation ON knowledge_sources FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE knowledge_ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_ingestion_jobs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS knowledge_jobs_tenant_isolation ON knowledge_ingestion_jobs;
CREATE POLICY knowledge_jobs_tenant_isolation ON knowledge_ingestion_jobs FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

ALTER TABLE agent_knowledge_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_knowledge_bindings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS agent_knowledge_bindings_tenant_isolation ON agent_knowledge_bindings;
CREATE POLICY agent_knowledge_bindings_tenant_isolation ON agent_knowledge_bindings FOR ALL TO ucve_app
    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    knowledge_bases, knowledge_sources, knowledge_ingestion_jobs,
    agent_knowledge_bindings TO ucve_app;
