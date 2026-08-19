# Voice Engine Plan — Stage 2 Implementation Package

Portable, self-contained implementation plan for the Unified Core Voice Engine (UCVE). This folder can be copied alongside a monorepo (or into one) and used as the authoritative execution guide for phases 00–35.

**Strategic reference (read-only):** `docs/blueprint/` (9-file suite) and `legacy_codebases/` (audit provenance).

**Execution (this folder):** phase specs, trackers, and phase tests.

## Trackers

| Tracker | Path | Purpose |
|---|---|---|
| Execution | [implementation_plan/EXECUTION_TRACKER.md](implementation_plan/EXECUTION_TRACKER.md) | Phase status, test script, human intervention, sign-off |
| Tests | [tests/phase_tests/TEST_TRACKER.md](tests/phase_tests/TEST_TRACKER.md) | Run commands, env vars, what each test checks |

## Running phase tests

From repository root (requires `pytest`; implementation modules under `core/` when built):

```bash
pytest voice_engine_plan/tests/phase_tests/ -v
pytest voice_engine_plan/tests/phase_tests/test_phase_17_pipeline_integration.py -v
python voice_engine_plan/scripts/verify_plan_integrity.py
```

## Phase index (00–35)

| Phase | Name | Spec |
|---:|---|---|
| 00 | Monorepo Planning Baseline | [phase_00](implementation_plan/phase_00_monorepo_planning_baseline.md) |
| 01 | Canonical Audio Types and Frame Contracts | [phase_01](implementation_plan/phase_01_canonical_audio_types_and_frame_contracts.md) |
| 02 | Stream Buffering and Backpressure Policy | [phase_02](implementation_plan/phase_02_stream_buffering_and_backpressure_policy.md) |
| 03 | Core Session FSM and Turn Lifecycle | [phase_03](implementation_plan/phase_03_core_session_fsm_and_turn_lifecycle.md) |
| 04 | Barge-In Arbitration and Recovery Rules | [phase_04](implementation_plan/phase_04_barge_in_arbitration_and_recovery_rules.md) |
| 05 | Provider Interface Contracts | [phase_05](implementation_plan/phase_05_provider_interface_contracts.md) |
| 06 | Provider Registry, Circuit Breakers, and Fallback Router | [phase_06](implementation_plan/phase_06_provider_registry_circuit_breakers_and_fallback_router.md) |
| 07 | Observability Foundations | [phase_07](implementation_plan/phase_07_observability_foundations.md) |
| 08 | Multi-Tenant Core Data Model and Isolation Boundaries | [phase_08](implementation_plan/phase_08_multi_tenant_core_data_model_and_isolation_boundaries.md) |
| 09 | Tenant Credential Vaulting and Secret Access Patterns | [phase_09](implementation_plan/phase_09_tenant_credential_vaulting_and_secret_access_patterns.md) |
| 10 | Compliance Architecture and Data Classification Model | [phase_10](implementation_plan/phase_10_compliance_architecture_and_data_classification_model.md) |
| 11 | Compliance Data Lifecycle (Retention/Deletion/Redaction) | [phase_11](implementation_plan/phase_11_compliance_data_lifecycle_retention_deletion_redaction.md) |
| 12 | Compliance Audit Trail and Access Logging | [phase_12](implementation_plan/phase_12_compliance_audit_trail_and_access_logging.md) |
| 13 | AuthN/AuthZ for Dashboard, API, and SDK | [phase_13](implementation_plan/phase_13_authn_authz_for_dashboard_api_and_sdk.md) |
| 14 | Usage Metering and Tenant Quotas | [phase_14](implementation_plan/phase_14_usage_metering_and_tenant_quotas.md) |
| 15 | Multilingual Language Registry and Routing Policies | [phase_15](implementation_plan/phase_15_multilingual_language_registry_and_routing_policies.md) |
| 16 | Text Normalization and Pronunciation Layer | [phase_16](implementation_plan/phase_16_text_normalization_and_pronunciation_layer.md) |
| 17 | Real-Time Orchestration Pipeline Integration | [phase_17](implementation_plan/phase_17_real_time_orchestration_pipeline_integration.md) |
| 18 | Telephony/SIP Base (Telnyx + Direct SIP) | [phase_18](implementation_plan/phase_18_telephony_sip_base_integration.md) |
| 19 | Telephony Abstraction and Secondary Trunk Readiness | [phase_19](implementation_plan/phase_19_telephony_abstraction_and_secondary_trunk_readiness.md) |
| 20 | Post-Call Intelligence Core Record Schema | [phase_20](implementation_plan/phase_20_post_call_intelligence_core_record_schema.md) |
| 21 | Structured Extraction and CRM Dispatch Contracts | [phase_21](implementation_plan/phase_21_structured_extraction_and_crm_dispatch_contracts.md) |
| 22 | Real-Time MCP Tooling Integration Layer | [phase_22](implementation_plan/phase_22_real_time_mcp_tooling_integration_layer.md) |
| 23 | Real-Time RAG and Knowledge Ingestion Contracts | [phase_23](implementation_plan/phase_23_real_time_rag_and_knowledge_ingestion_contracts.md) |
| 24 | Latency Budget Enforcement and SLO Policies | [phase_24](implementation_plan/phase_24_latency_budget_enforcement_and_slo_policies.md) |
| 25 | Error Taxonomy and Alerting Strategy | [phase_25](implementation_plan/phase_25_error_taxonomy_and_alerting_strategy.md) |
| 26 | Self-Serve Agent Builder Domain Model | [phase_26](implementation_plan/phase_26_self_serve_agent_builder_domain_model.md) |
| 27 | Self-Serve Agent Builder UX Flow Spec | [phase_27](implementation_plan/phase_27_self_serve_agent_builder_ux_flow_spec.md) |
| 28 | SDK/API Surface and Versioning Strategy | [phase_28](implementation_plan/phase_28_sdk_api_surface_and_versioning_strategy.md) |
| 29 | External Developer Experience and Documentation Spec | [phase_29](implementation_plan/phase_29_external_developer_experience_and_documentation_spec.md) |
| 30 | Deployment Topology and Environment Strategy | [phase_30](implementation_plan/phase_30_deployment_topology_and_environment_strategy.md) |
| 31 | Scaling and Runtime Resource Profiles | [phase_31](implementation_plan/phase_31_scaling_and_runtime_resource_profiles.md) |
| 32 | Security Hardening and Threat Controls | [phase_32](implementation_plan/phase_32_security_hardening_and_threat_controls.md) |
| 33 | End-to-End Validation Harness and Test Matrix | [phase_33](implementation_plan/phase_33_end_to_end_validation_harness_and_test_matrix.md) |
| 34 | Release Governance and Operational Runbooks | [phase_34](implementation_plan/phase_34_release_governance_and_operational_runbooks.md) |
| 35 | Stage-2 Plan Folder Finalization | [phase_35](implementation_plan/phase_35_stage_2_plan_folder_finalization.md) |

## Batch approval history

| Batch | Phases | Status |
|---|---|---|
| 1 | 00–04 | Approved — core foundation |
| 2 | 05–09 | Approved — providers, observability, tenant, vault |
| 3 | 10–14 | Approved — compliance early block, auth, metering |
| 4 | 15–21 | Approved — multilingual through CRM; **Phase 20 fix:** `caller_id` (E.164) on `CallRecord` |
| 5 | 22–28 | Approved — MCP, RAG, SLO, errors, builder, SDK |
| 6–7 | 29–35 | Autonomous completion — DX, deploy, scale, security, E2E, release, finalization |

## Portability

See [PORTABILITY_CHECKLIST.md](PORTABILITY_CHECKLIST.md). Plan revision log: [CHANGELOG_PLAN.md](CHANGELOG_PLAN.md).

**Dependency note:** Phase tests import implementation modules (`core/`, `post_call/`, etc.) when present; structural/doc phases pass without implementation.
