# Voice Engine Plan — Phase Test Tracker

Run from repo root. Requires `pytest` once implementation modules exist under `core/`.

| Phase | Test Script | What It Checks | Env Vars Needed | Manual Intervention Required | Run Command |
|---|---|---|---|---|---|
| 00 | test_phase_00_monorepo_baseline.py | Required dirs; uv workspace; `import core` | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_00_monorepo_baseline.py -v` |
| 01 | test_phase_01_canonical_audio_types.py | AudioFrame, branded IDs, frame cap | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_01_canonical_audio_types.py -v` |
| 02 | test_phase_02_stream_buffering.py | Bounded queues, overflow policy | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_02_stream_buffering.py -v` |
| 03 | test_phase_03_session_fsm.py | FSM transitions, turn lifecycle | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_03_session_fsm.py -v` |
| 04 | test_phase_04_barge_in.py | Barge-in arbitration, recovery | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_04_barge_in.py -v` |
| 05 | test_phase_05_provider_interfaces.py | Provider ABCs, config models | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_05_provider_interfaces.py -v` |
| 06 | test_phase_06_provider_registry.py | Registry, circuit breaker, failover | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_06_provider_registry.py -v` |
| 07 | test_phase_07_observability.py | Logging, metrics, tracing hooks | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_07_observability.py -v` |
| 08 | test_phase_08_multi_tenant_data_model.py | Tenant isolation, JSONB repos | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_08_multi_tenant_data_model.py -v` |
| 09 | test_phase_09_credential_vaulting.py | Vault refs, KMS stub | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_09_credential_vaulting.py -v` |
| 10 | test_phase_10_compliance_architecture.py | Classification registry; HIPAA BAA gate | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_10_compliance_architecture.py -v` |
| 11 | test_phase_11_compliance_data_lifecycle.py | Redaction; dual columns; daily purge | `DATABASE_URL`, `S3_ENDPOINT` (opt) | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_11_compliance_data_lifecycle.py -v` |
| 12 | test_phase_12_compliance_audit_trail.py | Immutability; on_audit_event hook | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_12_compliance_audit_trail.py -v` |
| 13 | test_phase_13_auth_access_control.py | HMAC; WSS token; RBAC; rate limit | `DATABASE_URL`, `REDIS_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py -v` |
| 14 | test_phase_14_usage_metering.py | 80/100% caps; 2min stale release; test_call_sec | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_14_usage_metering.py -v` |
| 15 | test_phase_15_multilingual_registry.py | LanguageRouter; ar/ms measure-only; RTL gate | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_15_multilingual_registry.py -v` |
| 16 | test_phase_16_text_normalization.py | Normalizer; 2-retry→fallback; English pass-through | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_16_text_normalization.py -v` |
| 17 | test_phase_17_pipeline_integration.py | E2E WS; VAD adapter; Redis; basic reconnect | `DATABASE_URL`, `REDIS_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py -v` |
| 18 | test_phase_18_telephony_sip_base.py | DirectSIP exit; caller ID; inbound-only | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py -v` |
| 19 | test_phase_19_telephony_abstraction.py | Single trunk default; Twilio stub; failover | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py -v` |
| 20 | test_phase_20_post_call_record_schema.py | CallRecord; caller_id; dual-channel; memory_embed | `DATABASE_URL`, `S3_ENDPOINT` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py -v` |
| 21 | test_phase_21_crm_dispatch.py | Review queue stub; WhatsApp stub; max_fields | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py -v` |
| 22 | test_phase_22_mcp_tooling.py | MCPHost; 3s timeout; serial; HTTP/SSE default | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py -v` |
| 23 | test_phase_23_realtime_rag.py | Tier embedder; conservative speculative; ingestion | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py -v` |
| 24 | test_phase_24_latency_slo.py | Warn-only SLO; playback_started; harness | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_24_latency_slo.py -v` |
| 25 | test_phase_25_error_alerting.py | Generic client errors; DLQ 30d; alerts | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py -v` |
| 26 | test_phase_26_agent_builder_domain.py | Autosave; config pin; publish validation | `DATABASE_URL` | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_26_agent_builder_domain.py -v` |
| 27 | test_phase_27_agent_builder_ux.py | Standalone SPA spec; sandbox test calls | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_27_agent_builder_ux.py -v` |
| 28 | test_phase_28_sdk_api_surface.py | OpenAPI; TS/Python SDK; Flutter roadmap | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_28_sdk_api_surface.py -v` |
| 29 | test_phase_29_developer_experience.py | Developer doc pack completeness | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_29_developer_experience.py -v` |
| 30 | test_phase_30_deployment_topology.py | docker-compose; worker torch deps | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_30_deployment_topology.py -v` |
| 31 | test_phase_31_scaling_profiles.py | Runtime profiles; admission caps | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_31_scaling_profiles.py -v` |
| 32 | test_phase_32_security_hardening.py | Threat model; anti-pattern checklist | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_32_security_hardening.py -v` |
| 33 | test_phase_33_e2e_validation.py | TEST_MATRIX 00–35; e2e harness | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_33_e2e_validation.py -v` |
| 34 | test_phase_34_release_governance.py | Runbooks; release governance | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_34_release_governance.py -v` |
| 35 | test_phase_35_plan_finalization.py | README; verify_plan_integrity.py | None | No — resolved | `pytest voice_engine_plan/tests/phase_tests/test_phase_35_plan_finalization.py -v` |

**Full suite:** `pytest voice_engine_plan/tests/phase_tests/ -v`

**Integrity check:** `python voice_engine_plan/scripts/verify_plan_integrity.py`
