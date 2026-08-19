# Phase 15: Multilingual Language Registry and Routing Policies

## 1. Executive Summary & Core Logic

Implement the language-pack registry, STT code-switching flags per language/tenant, and text-layer `LanguageRouter` debounce rules for Urdu, English, Arabic, Malay, and extensible additions. Primary harvest: MULTI (`legacy_codebases/Multilingual_AI_Voice_Agent_gittracked/backend/app/core/language_registry.py`, `language_router.py`, `backend/app/core/config/languages/{en,ur,ar,ms}.yaml`). Urdu STT defaults follow habiba measured CER (`legacy_codebases/habiba-sdk-agent/worker/providers/stt/gladia.py` — `code_switching=False`). Depends on Phase 05 STT config, Phase 06 provider chains, Phase 10 compliance tiers.

**Required checkpoint (from Phase 11):** document that Phase 11 regex redaction does **not** catch names/addresses in Urdu/Arabic script. This phase must add `core/compliance/redaction_limitations.md` cross-reference in registry docs and a `LanguageProfile.redaction_script_coverage` field marking `{ur, ar}` as `regex_partial` until script-aware NER is implemented `[FUTURE]`.

**Arabic/Malay code-switching:** no bespoke CS handling logic ships in v1 — production call volume in those languages is insufficient to calibrate against. Profiles carry `[MEASURE]` telemetry hooks; defaults stay conservative until CER measurement runs (same methodology as habiba Urdu CER 0.14 vs 0.43, File 04 §1).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| YAML language profiles | MULTI `languages/*.yaml` — auditable, non-code edits |
| `LanguageRegistry` singleton | Loaded at worker boot; tenant override merge |
| `LanguageRouter` near-verbatim port | MULTI debounce: ≥3 words immediate; <3 words need 2 consecutive detections |
| Per-language `code_switching` in agent config | File 04 §1 — habiba CER vs MULTI blanket True |
| Documented language-add workflow | Prevents ad hoc one-off language support |

**Reference docs:** blueprint File 04 §1–2; habiba `capabilities.py` language matrix.

## 3. What / How / Why

- **What:**
  - `LanguageProfile`: `{code, directive_prompt_path, vad_silence_override_ms, tts_voice_id, tts_first_chunk_word_count, script_direction, code_switching_default, redaction_script_coverage, cs_measure_only}` — `cs_measure_only=True` for `ar`/`ms` until CER data exists
  - `LanguageRegistry`: load YAML, validate codes, tenant merge from Phase 08 `agent_provider_config`
  - `LanguageRouter.route(transcript, current_language) -> str` — port MULTI logic (`language_router.py` lines 26–34: unsupported codes keep current)
  - Default profiles: `en`, `ur`, `ar`, `ms` from MULTI YAML (ur/ar `vad_silence_override_ms: 800`)
  - **Urdu defaults:** `code_switching=False` (habiba); **en:** `code_switching=True`; **ar/ms:** `code_switching=False` + `cs_measure_only=True` — emit Phase 07 metrics for CS utterance rate but **do not** add CS-specific STT/router branches until measurement phase
  - **`LanguageAddWorkflow` doc** (`core/language/profiles/ADDING_A_LANGUAGE.md`): required steps — (1) new YAML profile, (2) Phase 06 capability/registry entry for STT/TTS chains, (3) router fixture in `tests/fixtures/language_router/`, (4) RTL voice validation gate if `script_direction=rtl`
  - **RTL voice validation (required for Arabic):** `LanguageRegistry.validate_voice_for_publish(code, tts_voice_id)` — rejects agent publish if `ar` profile lacks a validated RTL-capable voice ID; not optional — silent breakage on RTL TTS is unacceptable
  - Emit `control.language_changed` event (Phase 08 wire vocabulary / File 08 §3)
- **How:** STT adapter reads `code_switching` from active profile at session start. Router runs on each STT final before LLM call (Phase 17). Directive injection uses profile `directive_prompt_path` via Phase 16 `prompt_builder`. On language switch: update TTS voice_id from profile; log via Phase 07 with `language_from`/`language_to`. `[MEASURE]` profiles increment `ucve_cs_utterance_total{language}` without changing routing logic.
- **Why this approach:** v3 locked Urdu-only output while STT allowed en+ur CS — script mismatch caused LLM "corrections" (AUDIT_01 §5). Router without registry caused habiba single-language-only production path. Building ar/ms CS handling before calibration repeats MULTI's blanket-True mistake. Alternative: Gladia-only LID — rejected; File 04 requires second STT in chain (Phase 06).

## Deliverables

- `core/language/__init__.py`
- `core/language/registry.py` — `LanguageRegistry`, `LanguageProfile`, `validate_voice_for_publish()`
- `core/language/router.py` — `LanguageRouter`, `LanguageRouterConfig`
- `core/language/profiles/en.yaml`
- `core/language/profiles/ur.yaml`
- `core/language/profiles/ar.yaml`
- `core/language/profiles/ms.yaml`
- `core/language/profiles/README.md` — includes **Phase 11 redaction limitation checkpoint**
- `core/language/profiles/ADDING_A_LANGUAGE.md` — **language-add workflow** (YAML + registry + fixture)
- `core/language/events.py` — `LanguageChangedEvent`
- `core/language/rtl_validation.py` — RTL voice ID gate for `ar`
- `tests/fixtures/language_router/` — MULTI-derived test cases + ar/ms measure-only fixtures

## 4. Compute & Resource Profile (if applicable)

Registry load: once at boot ~5 ms. Router: O(1) per final — < 0.05 ms. YAML profiles ~2 KB each — negligible memory. RTL validation: one registry lookup at publish — < 1 ms.

## 5. Compliance Notes (if applicable)

Language metadata is not PHI. Router logs must not include full transcript — Phase 07 rules. **Urdu/Arabic PHI redaction gap:** registry documents `redaction_script_coverage: regex_partial` for ur/ar — HIPAA tenants must acknowledge in onboarding docs until NER phase ships.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Arabic/Malay CS handling:** measure now via metrics/`[MEASURE]` flags; do **not** build CS-specific handling until CER-calibrated.
2. **Adding languages:** documented workflow — YAML profile + Phase 06 registry entry + test fixture (`ADDING_A_LANGUAGE.md`); no ad hoc code-only adds.
3. **RTL TTS voices:** **required** validation gate for Arabic at agent publish — not deferred to Phase 26 UI alone.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_15_multilingual_registry.py`
- **Asserts:** ≥3-word switch immediate; <3-word requires 2 consecutive; unsupported STT tag keeps current; ur default CS false; ar/ms have `cs_measure_only=True` and no CS router branches; registry loads 4 YAML profiles; redaction limitation doc links present; language_changed event emitted; `validate_voice_for_publish` rejects invalid ar voice; `ADDING_A_LANGUAGE.md` exists and lists 4 required steps.
- **Pass threshold:** 100% router tests from MULTI fixture set.
- **Latency target:** route() < 0.1 ms p99.
