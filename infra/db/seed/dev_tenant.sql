-- UCVE Local Development Seed Script (Non-Production)
-- Seeds initial test tenant, agent, and quota state.

INSERT INTO tenants (id, name, key_tier, allow_testing_providers, allowed_origins)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'Dev Local Tenant',
    'platform',
    true,
    ARRAY['http://localhost:3000', 'http://127.0.0.1:3000']
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO tenant_compliance_profile (tenant_id, compliance_tier, data_retention_days)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'standard',
    30
)
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO agents (id, tenant_id, name, system_prompt, agent_provider_config)
VALUES (
    'b1eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'Dev Test Assistant',
    'You are a helpful voice assistant.',
    '{
        "allow_testing_providers": true,
        "chains": [
            {"category": "stt", "language": "en", "priority": ["deepgram", "gladia"]},
            {"category": "llm", "language": "en", "priority": ["groq_llama3", "vllm_sovereign"]},
            {"category": "tts", "language": "en", "priority": ["uplift", "cartesia"]},
            {"category": "vad", "language": "en", "priority": ["silero", "energy_fallback"]}
        ]
    }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO quota_state (tenant_id, max_concurrent_sessions, monthly_seconds_limit, monthly_seconds_used)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    20,
    360000.0,
    0.0
)
ON CONFLICT (tenant_id) DO NOTHING;
