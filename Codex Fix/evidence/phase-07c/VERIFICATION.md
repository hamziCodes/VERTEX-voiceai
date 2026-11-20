# Phase 07C Verification — Stream-Safe Failover and Adapter Hardening

**Implementation date:** 2026-10-22

**Branch:** `wavia-fixv1`

**Rollback base:** `e180c0c`

**Implementation commit:** `ec1d47314360c70f8e0b9cdbba849e0392bee0dd` (`feat: make provider failover stream safe`).

**Status:** READY FOR FINAL QA

## Result

- `FailoverRouter.stream_with_failover` now owns streamed route selection,
  first-item/inter-item/overall deadlines, iterator cleanup, cancellation, and
  circuit evidence.
- A provider may fail over only before meaningful output. After text, tool
  intent, transcript text, or audio commits, the router raises a sanitized
  `ProviderStreamInterruptedError` and never starts the secondary.
- Batch STT, streamed LLM, and streamed TTS paths use the stream-aware router.
  TTS retains the client-visible interruption event after committed audio.
- Groq, Gemini, and OpenAI share one JSON-safe tool schema serializer and one
  fragmented-call accumulator. Malformed completed arguments become typed
  `invalid_output` failures instead of reaching a tool.
- OpenAI no longer accesses the nonexistent `LLMConfig.tool_choice` field.
- One turn suppresses repeated tool calls by call ID and canonical
  name/arguments identity, preventing duplicate side effects.
- All eight advertised batch adapters report local readiness from explicit
  mock mode or an injected credential. `health_check()` no longer always
  returns true in live mode.

## Automated verification

All pytest commands ran with `UCVE_ENV=test`, `RUN_MOCK_PROVIDERS=1`,
`RUN_LIVE_PROVIDERS=0`, and `RUN_LIVE_DB_TESTS=0`.

```text
pytest tests/providers tests/security/test_provider_credentials.py \
  tests/e2e/scenarios/test_failover_e2e.py \
  tests/listening/test_tool_loop.py -q
89 passed

pytest -q
626 passed, 1 skipped, 2 warnings

ruff check --select F,I,UP,B <all Phase 07C touched Python paths>
All checks passed

ruff check <all newly created Phase 07C Python paths>
All checks passed

python -m compileall -q <Phase 07C packages and tests>
Passed

python voice_engine_plan/scripts/verify_plan_integrity.py
OK: 36 phases, tests, and trackers verified.

git diff --check
Passed; only Windows LF-to-CRLF checkout notices were emitted.
```

The two warnings are existing hardening tests that deliberately use short HMAC
test keys. No provider request, telephony call, live database operation,
deployment, package publication, or paid traffic occurred.

## Failure-path evidence

- Primary failure before first output invokes the secondary exactly once.
- Primary failure after one committed item raises a typed interruption and
  does not invoke the secondary.
- First-item, inter-item idle, and overall deadline tests identify their stage.
- Cancellation closes the active iterator and does not attempt fallback.
- Empty/both-down streams produce sanitized `NoProviderAvailableError`
  evidence.
- Cross-adapter tests serialize tool schemas and reconstruct fragmented tool
  calls identically for Groq, Gemini, and OpenAI.
- A duplicated destructive tool call executes only once in a turn.
- Mock mode, live mode without a credential, and live mode with an injected
  credential have explicit readiness results for all advertised adapters.

## Security and scope review

- `.env` and raw API-key files were not opened.
- Credential-shaped literal scan: zero matches.
- Credential/authorization logging scan: zero matches.
- Production live-network-enable additions: zero matches.
- Forbidden-scope edits under `.github/workflows`, `legacy_codebases/`,
  `docs/blueprint/`, `.env`, or raw-key paths: zero matches.
- Stream errors contain provider/category/stage/count metadata only; they do
  not include response bodies, tool arguments, text, audio, or credentials.

## Deferred by design

- Live account, quota, latency, language, and voice-quality qualification needs
  a separately approved V5 run because it can incur cost.
- Durable credential persistence and distributed invalidation remain Phase 09.
- Tool discovery, authorization policy, MCP lifecycle, and business-specific
  idempotency persistence remain Phase 10.
- Final browser, WebSocket, multilingual listening, and telephony QA remains
  deferred until all phases are complete, as requested by Hamzi.

## Next exact action

Verify both local Phase 07C commit hashes and the worktree, then obtain Hamzi's
separate approval before pushing. Do not start Phase 08 before that checkpoint.
