# Phase 14: Usage Metering and Tenant Quotas

## 1. Executive Summary & Core Logic

Implement append-only usage metering and quota enforcement at session admission and during calls. Harvests habiba `usage_events` + `quota_state` schema (`legacy_codebases/habiba-sdk-agent/supabase/migrations/0001_schema.sql` lines 57–73) and emission logic (`legacy_codebases/habiba-sdk-agent/worker/usage.py` — kinds `stt_sec`, `tts_sec`, `llm_tokens`, `agent_sec`). Integrates with Phase 13 mint (reject when over quota) and Phase 08 repos. Billing productization (Stripe) remains out of scope — this phase delivers **metering truth** and **hard/soft caps**.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Append-only `usage_events` | habiba "billing truth" comment — `worker/usage.py` line 1 |
| `quota_state` fast counters | habiba mint reads concurrent + monthly minutes |
| Atomic increment in mint transaction | habiba `mint.py` — session row + quota in same txn |
| Worker shutdown flush via `asyncio.to_thread` | habiba sync psycopg pattern — avoid blocking event loop (fix D9) |
| Session heartbeat for crash release | Real-time call slots — 2 min TTL |

**Reference docs:** blueprint File 01 §3.3 UsageMeter; AUDIT_05 (usage absent in v3/MULTI/AWAZ).

## 3. What / How / Why

- **What:**
  - Usage kinds (unchanged from habiba): `stt_sec`, `tts_sec`, `llm_tokens`, `agent_sec`
  - Extended kinds `[NEW]`: `telephony_sec`, `storage_bytes`, `extraction_calls` (register now; emit in Phases 18–21); **`test_call_sec`** (sandbox test-call allowance — Phase 27; non-metered against production quota)
  - `QuotaLimits`: `max_concurrent`, `max_minutes_month`, `max_llm_tokens_month`, `rate_limit_per_min` (override Phase 13 default 120)
  - **Soft cap:** warn at **80%** monthly usage (webhook/log/metric — Phase 25 alerting expands). **Hard cap:** block mint at **100%**
  - `UsageMeter.record()` / `record_many()` — append events; skip zero quantities (habiba `record_usage_many` lines 46–48)
  - **Token metering flush:** **per-session by default** on `DISCONNECTED`; **per-turn flush** available via `UCVE_DEBUG_PER_TURN_METERING=true`
  - `QuotaEnforcer.check_mint(tenant_id)` — concurrent + monthly minutes
  - `QuotaEnforcer.release(session_id)` — decrement concurrent on session end
  - **Crash concurrent release:** heartbeat sweeper releases stale slots after **2 minutes** without worker heartbeat (not 5 — real-time admission starvation risk under crash load)
  - Monthly reset job — roll `quota_state.period_start` (habiba pattern)
- **How:** Mint path (Phase 13) calls `QuotaEnforcer` inside transaction before JWT. Worker collects per-session counters; on `DISCONNECTED` (Phase 03 FSM), flush via `record_many`. Heartbeat every 30 s extends session lease; missing 2 min → sweeper releases concurrent slot + Phase 12 audit `quota_slot_released_stale`. Use `asyncio.to_thread` for DB writes. Emit Phase 07 metrics `ucve_quota_reject_total`, `ucve_quota_soft_warn_total`.
- **Why this approach:** SaaS multi-tenancy requires admission control — habiba validated in production. v3/MULTI unbounded connections (AUDIT_01/03 §5) cannot ship. Alternative: post-hoc billing only — insufficient for runaway cost protection.

## Deliverables

- `core/metering/__init__.py`
- `core/metering/usage_meter.py` — `record`, `record_many`
- `core/metering/quota_enforcer.py`
- `core/metering/quota_limits.py`
- `core/metering/collector.py` — in-session counter aggregation
- `core/metering/heartbeat.py` — session heartbeat + 2 min stale sweeper
- `core/metering/kinds.py` — usage kind constants
- `infra/db/migrations/008_usage_quota_extend.sql` — soft/hard cap columns, heartbeat timestamp on sessions
- `worker-jobs/quota_monthly_reset.py`
- `worker-jobs/quota_stale_sweeper.py`
- `control-plane/routes/usage.py` — `GET /v1/usage` (tenant-scoped)

## 4. Compute & Resource Profile (if applicable)

Per session flush: 1 DB round trip, ~4 insert rows max — < 10 ms. Heartbeat: 30 s interval, ~200 bytes Redis key per session. Sweeper: O(stale sessions) every 60 s — negligible at <10k concurrent. Quota check on mint: < 5 ms p99.

## 5. Compliance Notes (if applicable)

Usage events contain no PHI — only tenant_id, session_id, quantities. Export for billing is tenant-scoped; Phase 12 audits admin usage views. GDPR: usage logs may be retained for billing legal basis after erasure request — document exception in Phase 11 policy.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Caps:** soft warn 80%; hard block mint at 100%.
2. **Token flush:** per-session default; per-turn debug flag.
3. **Crash release:** 2 min heartbeat timeout.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_14_usage_metering.py`
- **Asserts:** mint blocked at concurrent cap; soft warn at 80% monthly; hard block at 100%; session end writes usage rows; zero quantities skipped; concurrent released on disconnect; stale heartbeat releases slot at 2 min; monthly reset rolls counters; tenant A usage invisible to tenant B.
- **Pass threshold:** 100% quota + metering tests.
- **Latency target:** quota check < 5 ms p99; session flush < 15 ms p99.
