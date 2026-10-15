# Cleanup Phase Specifications

## C00 - Inventory and rollback point

Tasks:

- Confirm clean branch and matching local/remote commit.
- Inventory top-level packages, local artifacts, compatibility paths, legacy/reference trees, and duplicate implementations.
- Classify each item as active, compatibility, roadmap, reference, generated, or proven dead.
- Record Phase 00 handoff and known pre-existing failures.
- Commit this documentation before moving files.

Verification:

- `git branch --show-current`
- `git status --short`
- review all files in `Codex Fix/codebase-cleanup/`

Human intervention: none. This is documentation and read-only classification.

## C01 - Generated local clutter

Tasks:

- Resolve and validate every source and destination path inside the repository.
- Move `.pytest_cache`, `.ruff_cache`, and stale `.venv` to `hamza_local/clean_codebase/generated/<timestamp>/`.
- Leave active local tool state in place.
- Record paths, sizes, and reason in the quarantine manifest.

Verification:

- Confirm system `py -3.12` remains available.
- Run `py -3.12 -m pytest tests/latency -q`.
- Run an import/compile check without relying on the moved virtual environment.
- Confirm Git shows no tracked-file changes from this phase.

Human intervention: reinstall a clean `.venv` later only when dependency isolation is needed. This phase does not download packages.

## C02 - Proven duplicate tracked code

Tasks:

- Re-run import/reference searches for all old latency harness paths.
- Capture their Git object IDs and original paths.
- Move only unreferenced duplicates into `hamza_local/clean_codebase/tracked/latency-harnesses/`.
- Keep the canonical Phase 00 harness at `tests/latency/`.
- Update only current documentation that falsely points to removed runtime paths; preserve historical evidence as historical.

Verification:

- Run the Phase 00 latency suite.
- Run collection for root pytest configuration.
- Run Ruff and compile checks on affected packages.
- Inspect `git diff --check` and the deletion diff.

Human intervention: review the tracked deletion list before it is pushed. Git and the local quarantine both preserve recovery paths.

## C03 - Package and compatibility boundaries

Tasks:

- Validate root and child `pyproject.toml` workspace/package names.
- Trace Dockerfiles, Compose services, test contracts, and imports for every top-level service.
- Confirm whether `control-plane/` and `worker-raw/` must remain as compatibility directories.
- Document canonical underscore Python packages versus hyphenated distribution/service names.
- Identify empty initializers that are required for packaging.

Verification:

- Package metadata/build inspection without publishing.
- Focused Phase 00, packaging, hardening, and deployment-topology tests.
- Import checks for each canonical package.

Human intervention: required before renaming a public package, service, Docker image, or SDK import path.

## C04 - Minimal hierarchy realignment

Tasks:

- Apply only C03 changes proven safe by consumers and tests.
- Normalize misplaced implementation files into canonical underscore packages.
- Keep compatibility shims where public or test contracts require them.
- Update imports, Docker contexts, documentation links, and test paths atomically.

Verification:

- Run all directly affected suites, build metadata checks, and Docker configuration validation available offline.
- Compare module/import inventory before and after.
- Stop and roll back if a new failure appears.

Human intervention: approve any breaking public-path migration before implementation.

## C05 - Stubs, roadmap, and reference material

Tasks:

- Classify each stub as promised capability, internal roadmap, intentional interface, or abandoned code.
- Keep useful legacy agents available for latency comparison while excluding them from packages/test discovery.
- Verify `docs/archive`, `voice_engine_plan`, `agent-studio`, and `worker_managed` consumers.
- Quarantine only items with no code, test, build, documentation, or comparison purpose.

Verification:

- Reference scan, package manifest inspection, test collection, and documentation-link scan.
- No public capability may disappear silently.

Human intervention: decide whether roadmap capabilities should be implemented, hidden, or formally removed from product claims.

## C06 - Final offline verification

Tasks:

- Produce the final tree map and quarantine manifest.
- Run the largest safe offline test set and compare results with the known baseline.
- Run Ruff, compile, Git whitespace, ignored-secret, and package-content checks.
- Record anything intentionally retained and why.

Verification:

- Zero new test failures relative to baseline.
- No secrets staged or copied.
- No production Phase 01 code changed.
- Local quarantine remains ignored and recoverable.

Human intervention: run optional environment-specific Docker/UI checks if local services or browsers are required. Live calls remain a separate explicit approval gate.
