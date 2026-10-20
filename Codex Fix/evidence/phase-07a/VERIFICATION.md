# Phase 07A Verification — Provider Contracts and Typed Failures

**Implementation date:** 2026-10-20

**Branch:** `wavia-fixv1`

**Rollback base:** `b2f1ae0c41e06befe1b6fcd23daabd88e2d93983`

**Implementation commit:** pending Hamzi's required final commit approval

**Status:** READY FOR COMMIT APPROVAL

## Result

- One immutable catalog defines all eight advertised STT, LLM, and TTS
  provider identities and their checked-in adapter capabilities.
- Each specification records engine languages, stream shape, tool support,
  audio formats, current default models, compliance qualification, credential
  policy state, region policy, and rollout evidence state.
- All providers remain `offline_contract`, standard-compliance-only, and
  credential-policy `unresolved`; 07A does not invent H07 business decisions or
  claim live qualification.
- Provider factories, the registry, chain validation, and the published-agent
  compiler now use the same catalog.
- Unknown IDs, category mismatches, and engine-language mismatches fail closed.
  They no longer silently select Gladia, Groq, or Uplift.
- HTTP failures map to stable authentication, quota, rate-limit, timeout,
  invalid-request, transient-server, and permanent categories with explicit
  retryability and no provider response body storage.

## Test-driven evidence

- Initial catalog tests failed during collection because `ProviderSpec`,
  `UnknownProviderError`, and the failure taxonomy did not exist.
- Registry validation then failed because an unknown chain member was accepted.
- Public API validation then failed because the typed failures were not
  exported. Each red test passed after its corresponding minimal change.

## Automated verification

```text
pytest tests/providers tests/agents/test_session_plan_compiler.py -q
36 passed

UCVE_ENV=test RUN_MOCK_PROVIDERS=1 RUN_LIVE_PROVIDERS=0 \
  RUN_LIVE_DB_TESTS=0 pytest -q
561 passed, 1 skipped, 2 warnings

ruff check <Phase 07A Python paths>
All checks passed

python -m compileall -q core/providers control_plane/agents tests/providers
Passed

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.

git diff --check
Passed; only Windows LF-to-CRLF checkout notices were emitted.
```

The two warnings are existing hardening tests that deliberately use short HMAC
test keys. The evidence-bearing runs explicitly disabled live providers and
live database tests. No provider request or telephony call was made.

## Deferred by design

- H07 platform-key/BYOK and required release-chain decisions.
- Tenant credential resolution, rotation, and cache isolation (07B).
- Independent provider instances and scoped circuit evidence (07B).
- Stream commit/repair, tool normalization, and adapter deadline work (07C).
- Live provider qualification and any paid traffic (separate V5 approval).

## Security and scope review

- `.env` and raw API-key files were not opened.
- No secret value or provider response body is stored by the new contracts.
- `.github/workflows`, adapters, deployments, databases, and telephony were not
  modified.

## Rollback

Before commit, restore the tracked working tree to `b2f1ae0`. After an approved
commit, revert that implementation commit and its evidence update.
