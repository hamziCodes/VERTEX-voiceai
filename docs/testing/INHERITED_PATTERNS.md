# Inherited Test Patterns

Porting guidance from legacy repos (AUDIT_05 Rule 8). **Patterns only** — not literal file copies.

## habiba-sdk-agent

| Legacy pattern | UCVE equivalent |
|---|---|
| 60+ pytest modules + CI (AUDIT_04 §1) | `voice_engine_plan/tests/phase_tests/` per phase |
| Mint/HMAC integration tests | `test_phase_13_auth_access_control.py`, `examples/host-backend/` |
| Provider registry failover | `test_phase_06_provider_registry.py` |
| Cap exhaustion runbook | `docs/runbooks/RUNBOOK_QUOTA_EXHAUSTION.md` |
| Telephony webhook signature verify | `test_phase_18_telephony_sip_base.py`, `tests/security/test_anti_patterns.py` |
| Worker memory tuning (`OMP_NUM_THREADS=1`) | Phase 30/31 Docker + profiles |

Source citation: `legacy_codebases/habiba-sdk-agent/tests/`

## Multilingual_AI_Voice_Agent

| Legacy pattern | UCVE equivalent |
|---|---|
| `test_barge_in_verification.py` | `test_phase_04_barge_in.py`, E2E barge-in scenario |
| `test_orchestrator_arabic.py` | `test_phase_15_multilingual_registry.py`, `test_phase_16_text_normalization.py` |
| `test_replayable_iterator.py` | Phase 02 bounded buffer tests |
| Silero VAD runtime | Phase 17 pipeline + explicit torch in worker-raw Dockerfile |

Source citation: `legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/tests/`

## Not inherited

- v3 live-API scripts only (AUDIT_01)
- awaazlabs absent coverage (AUDIT_02) — gaps closed by Phase 25 DLQ + Phase 21 HMAC

## E2E harness

`tests/e2e/harness.py` composes mock providers + optional compose lifecycle — sovereign path without LiveKit coupling.
