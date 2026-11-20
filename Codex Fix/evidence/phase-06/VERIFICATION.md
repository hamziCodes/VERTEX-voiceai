# Phase 06 Verification — Published Agent Session Compiler

**Implementation date:** 2026-10-20

**Branch:** `wavia-fixv1`

**Rollback base:** `cbc9e3366d6dfab422eedea3517975ae14dbcf97`

**Implementation commit:** `5311b3c`

**Status:** READY FOR FINAL QA

## Result

- Published `AgentConfig` snapshots compile into frozen, schema-versioned,
  SHA-256-authenticated `RuntimeSessionPlan` values.
- Plans contain credential references only. Compiler validation rejects
  credential-shaped plaintext fields, unsupported providers, incomplete
  language chains, invalid voice mappings, and unpublished/cross-tenant data.
- Session mint pins the selected plan, language, and voice and signs their
  reference, version, and hash into the short-lived room token.
- The worker reconstructs the pinned snapshot and fails closed on missing
  sessions, identity mismatches, claim mismatches, or hash tampering.
- Published persona, provider, voice, language, and tool policy cannot be
  changed by a production session. Local development overrides require both a
  development/test environment and `UCVE_ALLOW_UNSAFE_SESSION_OVERRIDES=1`.
- An active v1 session remains on v1 when v2 is published; a new mint selects
  v2. Language routing and tool execution are constrained by the compiled plan.

## Automated verification

```text
pytest tests/agents/test_session_plan_compiler.py \
  tests/e2e/test_published_agent_runtime.py \
  tests/sdk/test_realtime_protocol.py -q
30 passed

UCVE_ENV=test RUN_MOCK_PROVIDERS=1 RUN_LIVE_PROVIDERS=0 \
  RUN_LIVE_DB_TESTS=0 pytest -q
546 passed, 1 skipped, 2 warnings

ruff check <new and substantially rewritten Phase 06 paths>
All checks passed

python -m compileall -q control_plane core worker_raw tests/agents \
  tests/e2e/test_published_agent_runtime.py
Passed

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.

git diff --check
Passed; only Windows LF-to-CRLF checkout notices were emitted.
```

The two warnings come from existing hardening tests that intentionally exercise
short HMAC test keys.

## Verification-process correction

An earlier full-suite attempt inherited workstation provider mode. Three
interruption tests logged a Gladia live-session connection before any audio was
submitted, then failed their timing assertions. No credential was printed or
read. The tests now force mock mode, and the evidence-bearing final full run
also forced mock providers and disabled live database tests at the command
level. No telephony call was placed.

## Known boundary and follow-up

The current in-memory repositories prove mint-to-worker authority and shared
repository/multi-worker semantics. PostgreSQL does not yet persist and reload
the complete runtime-plan snapshot across independent processes. Phase 09 owns
the durable agent-version and session-pin repositories and transaction. Until
then, this phase must not be represented as production-ready durability.

Pre-Phase-06 room tokens have a 120-second lifetime. Deployment must drain that
window before switching workers; the new worker deliberately rejects sessions
without an authenticated pinned plan instead of rebuilding them from defaults.

## Security and scope review

- `.env` and raw API-key files were not opened; no secret value was printed.
- Secret-shaped fields are rejected from compiled runtime plans.
- `.github/workflows`, deployment, publication, database migrations, and live
  telephony were not changed.
- Test-only secret strings remain limited to explicit fixtures.

## Rollback

Revert implementation commit `5311b3c` and its following evidence-only commit.
No external database migration or deployment state needs rollback.
