# Phase 33: End-to-End Validation Harness and Test Matrix

## 1. Executive Summary & Core Logic

Build the cross-phase end-to-end validation harness and explicit test matrix mapping every phase exit criterion to an automated or manual test — formalizing File 9 §3 benchmarking inheritance and porting **patterns** (not literal files) from habiba's 60+ pytest modules (AUDIT_04 §1, §6) and multilingual's targeted suites (`test_barge_in_verification.py`, `test_orchestrator_arabic.py`, AUDIT_03 §6). Unifies Phase 24 latency harness with functional E2E scenarios.

Depends on Phases 17–28 runtime paths, Phase 30 compose stack, Phase 24 `LatencyBenchmarkHarness`, Phase 32 security tests, all `voice_engine_plan/tests/phase_tests/`.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `pytest` + `pytest-asyncio` E2E suite | Consistent with phase_tests |
| Mock providers default; real-provider nightly `[LATER]` | File 9 §3 — CI cost control |
| Test matrix markdown ↔ pytest node ids | Traceability to EXECUTION_TRACKER |
| Synthetic audio fixtures only | Compliance — no real caller recordings |
| Compose-backed E2E optional job | Phase 30 stack |

**Reference docs:** blueprint File 09 §3.1–§3.3; AUDIT_05 §1 coverage matrix; habiba `tests/` layout.

## 3. What / How / Why

- **What:**
  - **`tests/e2e/harness.py`** — orchestrates: start mock WS server or compose stack → run scenario → assert phase criteria
  - **Core E2E scenarios (mock providers):**
    1. **Sovereign WS conversation** — 3-turn STT→LLM→TTS (Phase 17 exit)
    2. **Barge-in mid-TTS** — Phase 04 criteria
    3. **Provider failover** — kill primary STT mock (Phase 06)
    4. **Telephony inbound stub** — webhook → DirectSIP mock → pipeline (Phase 18)
    5. **MCP tool call serial + 3 s timeout** (Phase 22)
    6. **Post-call record + webhook** (Phases 20–21)
    7. **Agent publish + mint pin** (Phase 26)
  - **`tests/e2e/fixtures/audio/`** — synthetic PCM clips per language (en, ur short utterances)
  - **`docs/testing/TEST_MATRIX.md`** — table: Phase | Exit criterion | Test path | Auto/Manual
  - **`docs/testing/INHERITED_PATTERNS.md`** — maps habiba/multilingual tests to UCVE equivalents (AUDIT_05 Rule 8)
  - **Integration with Phase 24 harness** — E2E emits `LatencyWaterfall` per turn; warn-only assertion
  - **CI tiers:** `phase_tests` (fast, every PR); `e2e` (compose, main branch nightly)
- **How:** E2E uses null/mock provider adapters from Phase 05 test doubles. Telephony scenario uses recorded Telnyx webhook fixture (Phase 19 normalizer). Matrix generated to include all phases 00–35 with at least one verification row each (doc-only phases → file existence checks).
- **Why this approach:** AUDIT_05 shows no unified legacy harness — habiba strongest but LiveKit-coupled. UCVE needs sovereign E2E before release. Alternative: manual QA only — insufficient for 36 phases.

## Deliverables

- `tests/e2e/harness.py`
- `tests/e2e/scenarios/test_sovereign_conversation.py`
- `tests/e2e/scenarios/test_barge_in_e2e.py`
- `tests/e2e/scenarios/test_failover_e2e.py`
- `tests/e2e/scenarios/test_telephony_inbound_e2e.py`
- `tests/e2e/scenarios/test_post_call_e2e.py`
- `tests/e2e/fixtures/audio/` — synthetic clips
- `tests/e2e/conftest.py` — compose lifecycle optional fixture
- `docs/testing/TEST_MATRIX.md`
- `docs/testing/INHERITED_PATTERNS.md`
- `.github/workflows/e2e-nightly.yml` — stub

## 4. Compute & Resource Profile (if applicable)

Mock E2E full suite: ~2–5 min CI. Compose E2E nightly: ~15 min. Latency benchmark 10-turn: ~30 s (Phase 24). Real-provider nightly `[LATER]`: ~5 min additional.

## 5. Compliance Notes (if applicable)

E2E fixtures synthetic only — no production PHI. Test matrix marks HIPAA scenarios as manual BAA ack required. Recorded webhook fixtures use sanitized caller_id.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Real provider E2E in CI:** **nightly optional job `[LATER]`** — mock providers gate every PR; real keys too flaky/costly for PR path.
2. **Coverage target:** **100% phase row in TEST_MATRIX** — not 100% line coverage (unrealistic pre-GA).
3. **LiveKit E2E:** **optional scenario only** — not in default sovereign PR suite (Phase 18).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_33_e2e_validation.py`
- **Asserts:** TEST_MATRIX.md covers phases 00–35; each E2E scenario file exists; harness.py importable; INHERITED_PATTERNS cites habiba + multilingual sources; synthetic audio fixtures present; e2e-nightly workflow stub exists; matrix links to phase_tests paths.
- **Pass threshold:** structural + harness smoke (mock 1-turn) when implementation exists.
- **Latency target:** mock sovereign conversation E2E < 60 s total.
