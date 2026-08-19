# Release Governance

Semver platform releases aligned with Phase 28 SDK/API versioning.

## Promotion path

```text
dev → staging → prod
```

| Gate | Requirement |
|---|---|
| CI | All `voice_engine_plan/tests/phase_tests/` green |
| Staging E2E | Phase 33 mock scenarios on staging deploy |
| Security | Phase 32 [PENTEST_READINESS.md](../security/PENTEST_READINESS.md) sign-off |
| Matrix | [TEST_MATRIX.md](../testing/TEST_MATRIX.md) — all phases ≥ structural pass |
| Prod approval | Manual GitHub environment + documented two-person rule |

## Versioning

- Platform: `MAJOR.MINOR.PATCH` (Conventional Commits → [CHANGELOG.md](../../CHANGELOG.md))
- API: `/v1/` until breaking REST change
- SDK: lockstep minor with server; patch hotfixes allowed independently (Phase 28)

## Pre-GA requirement

`voice_engine_plan/implementation_plan/EXECUTION_TRACKER.md` — all phases ≥ `READY_FOR_MANUAL_TEST`.

## Deploy workflows

- `.github/workflows/deploy-staging.yml` — auto on main `[stub]`
- `.github/workflows/deploy-prod.yml` — manual approval `[stub]`

## Rollback reference

See [ROLLBACK.md](ROLLBACK.md) for image tag rollback and config pin behavior.

## Incident follow-up

Use [IncidentTemplate.md](IncidentTemplate.md) within 5 business days of SEV-1/SEV-2.
