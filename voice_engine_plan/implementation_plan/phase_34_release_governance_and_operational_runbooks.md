# Phase 34: Release Governance and Operational Runbooks

## 1. Executive Summary & Core Logic

Define release governance (versioning, promotion gates, rollback), operational runbooks for on-call scenarios, and incident response playbooks — extending habiba's runbook pattern (`legacy_codebases/habiba-sdk-agent/docs/60-RUNBOOK-CAP-EXHAUSTION.md`, `63-GUIDE-WORKER-DEPLOYMENT-DEFERRAL.md`, AUDIT_04 §1) to full UCVE multi-tenant operations. Wires Phase 25 alerting (email/webhook) into runbook triggers and Phase 33 test matrix into release gates.

Depends on Phase 25 AlertRouter, Phase 30 environments, Phase 31 scaling profiles, Phase 32 security checklist, Phase 28 SDK versioning policy, Phase 14 quota runbooks.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Semver for platform releases | Aligns Phase 28 SDK/API versioning |
| Release checklist gate before prod | Phase 33 matrix + Phase 32 pentest readiness |
| Runbook one-scenario-per-file | habiba numbered runbook pattern |
| Rollback = redeploy previous image tag | Container-native (Phase 30) |
| Change log in `CHANGELOG.md` | Conventional Commits aggregation |

**Reference docs:** habiba `.github/workflows/{deploy-staging,deploy-prod,release-sdk}.yml`; File 09 §4.3 CI/CD.

## 3. What / How / Why

- **What:**
  - **`docs/runbooks/README.md`** — index + severity definitions (aligned Phase 25)
  - **Runbooks (minimum set):**
    - `RUNBOOK_QUOTA_EXHAUSTION.md` — port habiba cap exhaustion (Phase 14 80/100%)
    - `RUNBOOK_PROVIDER_OUTAGE.md` — Phase 06 failover + manual promotion
    - `RUNBOOK_TRUNK_FAILOVER.md` — Phase 19 single vs dual trunk
    - `RUNBOOK_DLQ_BACKLOG.md` — Phase 25 DLQ sweeper + 30-day retention
    - `RUNBOOK_LATENCY_SLO_BREACH.md` — Phase 24 warn-only interpretation
    - `RUNBOOK_HIPAA_INCIDENT.md` — PHI exposure suspicion; Phase 12 audit pull
    - `RUNBOOK_WORKER_OOM.md` — Phase 31 profile tuning
  - **`docs/release/RELEASE_GOVERNANCE.md`** — dev→staging→prod promotion; required checks: CI green, Phase 33 E2E on staging, Phase 32 checklist sign-off
  - **`docs/release/ROLLBACK.md`** — image tag rollback; config pin implications (active sessions keep pinned config)
  - **`CHANGELOG.md`** — root, Keep a Changelog format
  - **`.github/workflows/deploy-staging.yml`** + **`deploy-prod.yml`** — stubs extending habiba pattern; manual approval gate prod
  - **`IncidentTemplate.md`** — post-incident review structure
- **How:** Runbooks reference exact metrics/alerts (Phase 07/25). Release governance requires EXECUTION_TRACKER all phases ≥ `READY_FOR_MANUAL_TEST` before GA tag. Staging deploy runs e2e-nightly suite. Prod deploy requires two-person approval documented (process, not automated in v1).
- **Why this approach:** awaazlabs had no operational docs (AUDIT_02). Habiba runbooks prove format works. **PagerDuty integration deferred** (Phase 25) — email/webhook runbook triggers sufficient for v1 ops.

## Deliverables

- `docs/runbooks/README.md`
- `docs/runbooks/RUNBOOK_QUOTA_EXHAUSTION.md`
- `docs/runbooks/RUNBOOK_PROVIDER_OUTAGE.md`
- `docs/runbooks/RUNBOOK_TRUNK_FAILOVER.md`
- `docs/runbooks/RUNBOOK_DLQ_BACKLOG.md`
- `docs/runbooks/RUNBOOK_LATENCY_SLO_BREACH.md`
- `docs/runbooks/RUNBOOK_HIPAA_INCIDENT.md`
- `docs/runbooks/RUNBOOK_WORKER_OOM.md`
- `docs/release/RELEASE_GOVERNANCE.md`
- `docs/release/ROLLBACK.md`
- `docs/release/IncidentTemplate.md`
- `CHANGELOG.md`
- `.github/workflows/deploy-staging.yml`
- `.github/workflows/deploy-prod.yml`

## 4. Compute & Resource Profile (if applicable)

Runbooks doc-only. Deploy workflows: staging ~10 min; prod ~15 min including manual gate wait (human time not counted).

## 5. Compliance Notes (if applicable)

HIPAA incident runbook defines breach notification timeline placeholders (legal review required). Runbooks must not instruct operators to log PHI during incidents — correlation_id only. DLQ runbook respects 30-day retention + legal hold exception (Phase 25/11).

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Prod deploy approval:** **manual GitHub environment gate + documented two-person rule** — not automated SOX tooling in v1.
2. **Runbook delivery channel:** **in-repo Markdown** — same portability as `voice_engine_plan/`; not Notion/Confluence external.
3. **SDK release cadence:** **lockstep with server minor releases** — Phase 28 policy; hotfix SDK patches allowed independently for client bugs.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_34_release_governance.py`
- **Asserts:** all 7 runbooks exist; README indexes them; RELEASE_GOVERNANCE references Phase 33 matrix; ROLLBACK documents config pin behavior; CHANGELOG.md exists; deploy workflow stubs exist; QUOTA runbook references Phase 14 80/100% thresholds.
- **Pass threshold:** 100% runbook inventory checks.
- **Latency target:** N/A (documentation phase).
