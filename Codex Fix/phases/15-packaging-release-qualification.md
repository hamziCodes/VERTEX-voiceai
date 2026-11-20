# Phase 15 — Packaging and Production Release Qualification

**Status:** COMPLETE (OFFLINE) 2026-11-16 — H15 live/publish/deploy/spend approvals await Hamzi. Evidence: `Codex Fix/evidence/phase-15/`. Package/container commands as finalized: `scripts/release/` (render_dockerfiles, export_requirements, export_openapi, container_stack, qualify_sdks, drills, run_live_db_tests, license_report, live_certification).

**Goal:** Produce installable, deployable, documented artifacts and a release evidence bundle for each chosen deployment model, without publishing or deploying until Hamzi approves.

**Depends on:** All phases required by the selected release scope.

**Audit coverage:** S01/S02 final, I01/I12/I14 final, T06 docs, deployment-model acceptance.

## Human gate before implementation

Resolve H15 only after all offline artifacts exist. Approval is required separately for live provider tests, live calls, package publishing, staging deploy, production deploy, and any spend.

## Tasks

- [ ] Fix container COPY/import/assets so control plane, worker, post-call/jobs and optional telephony build from a clean checkout.
- [ ] Pin/reconcile dependency manifests and lock strategy; perform approved dependency vulnerability/license scan without changing workflows.
- [ ] Build Python wheel/sdist and TS packages; install in isolated consumers and run documented quickstarts.
- [ ] Exclude legacy code, caches, virtualenvs, secrets and unnecessary context from distributable artifacts/images.
- [ ] Generate OpenAPI/realtime/config docs from runtime contracts; compare all examples and remove unsupported promises.
- [ ] Run fresh database install plus upgrade, Redis restart, service restart, network failure, provider failure, job retry and rollback drills.
- [ ] Run full offline test matrix and latency corpus; record commit, artifacts, hashes, versions, p50/p95/p99, known limitations and accepted risks.
- [ ] Qualify separately: packaged SDK, managed enterprise deployment, and self-serve dashboard. Each gets its own checklist and “not included” list.
- [ ] Prepare live-provider/carrier certification commands and cost limits but do not execute them.
- [ ] Prepare release notes, rollback plan, version compatibility matrix and support/runbook handoff.
- [ ] Ask Hamzi for explicit V5/V6 approvals. Execute only approved actions, then append sanitized evidence.

## Verification

```powershell
python -m pytest tests voice_engine_plan/tests/phase_tests -q
# Exact package/container commands are finalized during implementation and recorded here.
git diff --check
git status --short
```

Expected: all selected release gates pass from clean checkout with no secret files; artifacts install; containers become ready; no live network required for offline qualification.

## Release blockers

- Any critical/high finding without accepted risk.
- Missing truthful latency evidence.
- Production mock/fake-success path.
- Failed tenant isolation or migration.
- Advertised stub/unsupported SDK/provider/carrier.
- Missing rollback or incomplete retention/erasure for promised compliance.
- Missing explicit approval for paid/live/publish/deploy action.

## Exit criteria

- Hamzi receives a concrete release candidate and evidence bundle to approve.
- Publishing/deployment occurs only after approval and is followed by smoke/rollback checks.
- Production status describes exactly what passed, what was excluded, and what remains roadmap.
