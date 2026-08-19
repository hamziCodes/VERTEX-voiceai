# Phase 00: Monorepo Planning Baseline

## 1. Executive Summary & Core Logic

Establish the canonical repository layout, naming conventions, and cross-module import boundaries before any runtime code lands. This phase produces no voice logic; it defines where `core/`, `control-plane/`, `worker-raw/`, and shared test harnesses live so every subsequent phase writes to a stable address. Sits at the foundation of the UCVE monorepo described in blueprint File 09 §1, adapted to this workspace's existing `legacy_codebases/` (read-only) and `docs/blueprint/` (reference) trees.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Python 3.12 (worker/control-plane) | Matches habiba production baseline (AUDIT_04); async-first for pipeline |
| `uv` workspace | Monorepo dependency isolation with shared `core` editable install (decided) |
| `ruff` + `mypy` (strict on `core/`) | Enforces interface contracts early; habiba CI pattern extended |
| `pytest` + `pytest-asyncio` | Standard for async pipeline tests; habiba has 60+ test modules |
| Conventional Commits + phase tags | Traceability to `voice_engine_plan/` phase index |

**Reference docs:** blueprint File 09 §1 (directory tree), PEP 420 namespace packages if multi-package layout chosen.

## 3. What / How / Why

- **What:** Root monorepo skeleton with `core/`, `control-plane/`, `worker-raw/`, `tests/phase_tests/`, `infra/docker/`, and `pyproject.toml` workspace root. Artifact contract: every phase delivers code + test under predictable paths; phase index maps 1:1 to `voice_engine_plan/implementation_plan/phase_XX_*.md`.
- **How:** Scaffold empty package dirs with `__init__.py` only where needed; add root `README.md` stub pointing to blueprint; configure workspace so `from core.types import AudioFrame` resolves without PYTHONPATH hacks; pin Python version in `.python-version` and Docker base image reference.
- **Why this approach:** All four legacy repos used ad hoc layouts (v3 flat FastAPI, habiba multi-folder without shared lib). A single monorepo with explicit `core/` at the **workspace root** (alongside `legacy_codebases/`, not nested) prevents the habiba trap (orchestrator locked to LiveKit worker path) and the v3 trap (concrete classes in transport). Alternative considered: polyrepo per service — rejected for a small team because shared types (Phases 01–04) would duplicate and drift.

## Deliverables

- `pyproject.toml` — uv workspace root, `core` editable package
- `uv.lock`
- `.python-version` — pinned to 3.12
- `README.md` — root stub linking to `docs/blueprint/` and `voice_engine_plan/`
- `core/__init__.py`
- `core/compliance/__init__.py` — empty placeholder
- `control-plane/__init__.py`
- `worker-raw/__init__.py`
- `tests/__init__.py`
- `infra/docker/.gitkeep`
- Ruff + mypy config (in `pyproject.toml` or `ruff.toml` / `mypy.ini`)

## 4. Compute & Resource Profile (if applicable)

Dev machine: 8 GB RAM minimum for Silero pool later; no GPU required for Phase 00. CI runner: 2 vCPU / 4 GB RAM sufficient for lint + structural tests.

## 5. Compliance Notes (if applicable)

None at scaffold level. Phase 00 must reserve `core/compliance/` placeholder path (empty) so compliance modules are not bolted into `worker-raw/` later.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions recorded for traceability:

1. **Package manager:** `uv` (confirmed).
2. **Repo layout:** top-level folders alongside `legacy_codebases/` (confirmed).
3. **TypeScript SDK location:** deferred to Phase 28 (no decision required now).

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_00_monorepo_baseline.py`
- **Asserts:** required top-level dirs exist (`core/`, `control-plane/`, `worker-raw/`, `tests/`); `pyproject.toml` declares workspace; `ruff`/`mypy` configs present; import smoke test `import core` succeeds.
- **Pass threshold:** 100% structural checks green; import smoke < 2 s.
- **Latency target:** N/A (structural only).
