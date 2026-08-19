# Voice Engine Plan — Portability Checklist

Verify before copying `voice_engine_plan/` to another workspace.

- [x] `README.md` indexes all phases 00–35
- [x] `implementation_plan/` contains exactly 36 `phase_XX_*.md` files
- [x] `tests/phase_tests/` contains one test script per phase
- [x] `EXECUTION_TRACKER.md` has 36 data rows
- [x] `TEST_TRACKER.md` lists all test scripts
- [x] `scripts/verify_plan_integrity.py` passes from repo root
- [x] No absolute filesystem paths in phase specs (legacy paths use `legacy_codebases/` relative form)
- [x] All phases §6 resolved — no open ambiguity questions
- [x] Batch 4 fix applied: Phase 20 `caller_id` on `CallRecord`
- [x] Batch 5 decisions applied: Phases 22–28
- [x] Phases 29–35 drafted with resolved §6 decisions

**External dependencies when running tests:** repository root `core/`, `post_call/`, `infra/` implementation modules (optional until build phases complete).

**Self-contained within folder:** phase specs, trackers, tests, integrity script, README, CHANGELOG_PLAN.
