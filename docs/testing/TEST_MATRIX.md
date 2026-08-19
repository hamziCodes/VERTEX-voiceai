# UCVE Test Matrix

Maps each phase exit criterion to verification (Phase 33). Auto = pytest; Manual = human sign-off.

| Phase | Exit criterion | Test path | Auto/Manual |
|---|---|---|---|
| 00 | Monorepo baseline layout | voice_engine_plan/tests/phase_tests/test_phase_00_monorepo_baseline.py | Auto |
| 01 | Canonical audio types + frame contracts | voice_engine_plan/tests/phase_tests/test_phase_01_canonical_audio_types.py | Auto |
| 02 | Stream buffering + backpressure | voice_engine_plan/tests/phase_tests/test_phase_02_stream_buffering.py | Auto |
| 03 | Session FSM + turn lifecycle | voice_engine_plan/tests/phase_tests/test_phase_03_session_fsm.py | Auto |
| 04 | Barge-in arbitration + recovery | voice_engine_plan/tests/phase_tests/test_phase_04_barge_in.py | Auto |
| 05 | Provider interface contracts | voice_engine_plan/tests/phase_tests/test_phase_05_provider_interfaces.py | Auto |
| 06 | Provider registry + circuit breakers | voice_engine_plan/tests/phase_tests/test_phase_06_provider_registry.py | Auto |
| 07 | Observability foundations | voice_engine_plan/tests/phase_tests/test_phase_07_observability.py | Auto |
| 08 | Multi-tenant data model + isolation | voice_engine_plan/tests/phase_tests/test_phase_08_multi_tenant_data_model.py | Auto |
| 09 | Credential vaulting + secret access | voice_engine_plan/tests/phase_tests/test_phase_09_credential_vaulting.py | Auto |
| 10 | Compliance architecture + classification | voice_engine_plan/tests/phase_tests/test_phase_10_compliance_architecture.py | Auto |
| 11 | Data lifecycle retention/deletion | voice_engine_plan/tests/phase_tests/test_phase_11_compliance_data_lifecycle.py | Auto |
| 12 | Audit trail + access logging | voice_engine_plan/tests/phase_tests/test_phase_12_compliance_audit_trail.py | Auto |
| 13 | AuthN/AuthZ dashboard API + SDK | voice_engine_plan/tests/phase_tests/test_phase_13_auth_access_control.py | Auto |
| 14 | Usage metering + tenant quotas | voice_engine_plan/tests/phase_tests/test_phase_14_usage_metering.py | Auto |
| 15 | Multilingual registry + routing | voice_engine_plan/tests/phase_tests/test_phase_15_multilingual_registry.py | Auto |
| 16 | Text normalization + pronunciation | voice_engine_plan/tests/phase_tests/test_phase_16_text_normalization.py | Auto |
| 17 | Real-time orchestration pipeline | voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py | Auto |
| 18 | Telephony SIP base integration | voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py | Auto |
| 19 | Telephony abstraction + dual trunk | voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py | Auto |
| 20 | Post-call record schema | voice_engine_plan/tests/phase_tests/test_phase_20_post_call_record_schema.py | Auto |
| 21 | Structured extraction + CRM dispatch | voice_engine_plan/tests/phase_tests/test_phase_21_crm_dispatch.py | Auto |
| 22 | Real-time MCP tooling layer | voice_engine_plan/tests/phase_tests/test_phase_22_mcp_tooling.py | Auto |
| 23 | Real-time RAG + KB ingestion | voice_engine_plan/tests/phase_tests/test_phase_23_realtime_rag.py | Auto |
| 24 | Latency budget + SLO policies | voice_engine_plan/tests/phase_tests/test_phase_24_latency_slo.py | Auto |
| 25 | Error taxonomy + alerting | voice_engine_plan/tests/phase_tests/test_phase_25_error_alerting.py | Auto |
| 26 | Agent builder domain model | voice_engine_plan/tests/phase_tests/test_phase_26_agent_builder_domain.py | Auto |
| 27 | Agent builder UX flow spec | voice_engine_plan/tests/phase_tests/test_phase_27_agent_builder_ux.py | Auto |
| 28 | SDK/API surface + versioning | voice_engine_plan/tests/phase_tests/test_phase_28_sdk_api_surface.py | Auto |
| 29 | External developer experience docs | voice_engine_plan/tests/phase_tests/test_phase_29_developer_experience.py | Auto |
| 30 | Deployment topology + environments | voice_engine_plan/tests/phase_tests/test_phase_30_deployment_topology.py | Auto |
| 31 | Scaling + runtime profiles | voice_engine_plan/tests/phase_tests/test_phase_31_scaling_profiles.py | Auto |
| 32 | Security hardening + threat controls | voice_engine_plan/tests/phase_tests/test_phase_32_security_hardening.py | Auto |
| 33 | E2E validation harness + matrix | voice_engine_plan/tests/phase_tests/test_phase_33_e2e_validation.py | Auto |
| 34 | Release governance + runbooks | voice_engine_plan/tests/phase_tests/test_phase_34_release_governance.py | Auto |
| 35 | Plan folder finalization | voice_engine_plan/tests/phase_tests/test_phase_35_plan_finalization.py | Auto |

## E2E scenarios (mock providers)

| Scenario | Test path |
|---|---|
| Sovereign WS 3-turn conversation | tests/e2e/scenarios/test_sovereign_conversation.py |
| Barge-in mid-TTS | tests/e2e/scenarios/test_barge_in_e2e.py |
| Provider failover | tests/e2e/scenarios/test_failover_e2e.py |
| Telephony inbound stub | tests/e2e/scenarios/test_telephony_inbound_e2e.py |
| Post-call + webhook | tests/e2e/scenarios/test_post_call_e2e.py |

Orchestrator: `tests/e2e/harness.py`

## CI tiers

- **PR:** `voice_engine_plan/tests/phase_tests/` (fast)
- **Main/nightly:** compose-backed E2E `[LATER]`
