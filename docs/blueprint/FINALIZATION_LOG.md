# UCVE Blueprint Finalization Log

**Pass 1 date:** 2026-08-15 (audit-only; trees absent)  
**Pass 2 date:** 2026-08-17 (live `file:line` against `legacy_codebases/`)  
**Scope:** Reconciliation only — save 9 blueprint files, verify against `AUDIT_01`–`AUDIT_05`, then spot-check live source, correct factual/cross-ref issues, stop.  
**Audit corpus:** `/workspace/auit_docs/AUDIT_01_AI_VOICE_AGENT_V3.md` … `AUDIT_05_SYNTHESIS_AND_FEATURE_MATRIX.md` (present).  
**Legacy codebases (pass 2):** `/workspace/legacy_codebases/{AI_voice_agent_v3 - gemini,awaazlabs,Multilingual_AI_Voice_Agent_gittracked,habiba-sdk-agent}/` (present on `main` as of `3e9697a`).

---

## File 01 — `01_SYSTEM_TOPOLOGY_AND_ARCHITECTURE.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §1 | Typo `gittracged` | → `gittracked` | AUDIT_03 / AUDIT_05 on-disk name |
| §2.2 provenance table | LangRouter cited AUDIT_03 §2, §6 | → AUDIT_03 §1, §3 language | AUDIT_03 §1 tree, §3 language |
| §2.2 provenance table | Extractor cited AUDIT_02 §2, §3 | → AUDIT_02 §1, §2 LLM | AUDIT_02 §1 |
| §2.2 provenance table | UsageMeter lumped as `[NEW]` with Redis/RAG/MCP | Split: Redis/RAG/MCP remain `[NEW]`; UsageMeter grounded in habiba usage path | AUDIT_05 §3 (usage metering not a four-repo gap); AUDIT_04 §1 tree `usage.py`, §4 admin |
| §3.2 | Silero pool Lock cited only §2 | Cite AUDIT_03 §1 (pool+Lock) + §2 | AUDIT_03 §1 |
| §3.4 | Bare `barge_in`/`hangup`/`ping`; pointed to File 7 §4 | Unified `control.*` names; pointer → File 8 §3 | File 8 §3 vocab table |
| §3.5 | Modularity justification #1 for HMAC/RLS | → justification #2 (transport split); #1 is registry | AUDIT_04 §6 |
| §4 | Benchmarking harness “File 8” | → File 9 §3 | File 9 §3 |
| §4 STT row | “Gladia 0.2s in three of four” | Clarify Gladia in v3+MULTI; habiba is LiveKit `endpointing.min_delay` | AUDIT_01/03 §2 STT; AUDIT_04 §2 VAD |
| §4 chunker row | 2-word TTFT cited AUDIT_03 §5 | → AUDIT_03 §2 + AUDIT_05 §2 | AUDIT_03 §2; AUDIT_05 §2 |
| §5 | “full tree in File 8” | → File 9 §1 (+ provenance note) | File 9 §1; File 1 §6 index |

---

## File 02 — `02_CORE_AUDIO_ENGINE_AND_STATE_MACHINE.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §1.1 transcript queue | Claimed unbounded in **both** v3 and multilingual; dead link to §1.3 | v3 unbounded (AUDIT_01 §5); MULTI `_SentenceBridge` maxsize 50; drop bad §1.3 ref | AUDIT_01 §5; AUDIT_03 §3/§5 |
| §2.1 FSM | Edge used bare `hangup` | → `control.hangup / [END_CALL] / …` | File 8 §3 |
| §2.2 | Invalid-transition quote cited AUDIT_03 §6 | Primary cite AUDIT_03 §3 (quote); §6 restates “does not enforce guards” | AUDIT_03 §3 state table; §6 debt table |
| §3.1 sequence | 700ms cited §2; UCVE emit `control{action: barge_in}` | Cite §3; emit `control.barge_in`; legacy shape kept in provenance column | AUDIT_03 §3; File 8 §3 |
| §3.2 | Abstract `barge_in` | → `control.barge_in` + File 8 §3 | File 8 §3 |
| §5 | Flat list 1–4; File 9 linked §5.1–§5.4 | Renumbered to §5.1–§5.4 so checklist links resolve | File 9 §5 |

---

## File 03 — `03_PLUGGABLE_PROVIDER_ABSTRACTION.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §2 `STTConfig` | `code_switching` default `True` conflicted with File 4/8 | Default `False` + note | File 4 §1; File 8 `languageProfile`; AUDIT_04 §2 CER |
| §2 `Transcript` | Overclaimed Gladia always provides confidence | Softened; AUDIT_01 §5 language unread / confidence threshold unused | AUDIT_01 §5 |
| §2 `VADConfig` | Implied multilingual shares 250ms silence default | Clarify v3 default vs MULTI overrides/unused commit ms | AUDIT_01 §2; AUDIT_03 §2 |
| §2 TTS / cancel | `CancellationToken` referenced, undefined; File 4 SSML fields absent | Added `CancellationToken` Protocol; optional `rate`/`pitch`/`emphasis_spans` | File 2 §3.3; File 4 §5 |
| §3 TypeScript | Incomplete mirror of Python configs | Added encoding / historyTokenBudget / maxRetries / SSML optionals; CS default note | Consistency with §2 |

---

## File 04 — `04_MULTILINGUAL_AND_CODE_SWITCHING_ENGINE.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §1 | Implied File 3 CS default aligned | Explicit File 3 default `False` | File 3 edit above |
| §2.1 | “Gladia CS used by three of four”; “Deepgram language detection” | Gladia used by three; CS-on only in two; Deepgram LID NOT VERIFIED | AUDIT_01/03/04 §2; AUDIT_04 §5 |
| §2.2 | Debounce cited “§1 orchestration” | Prefer AUDIT_03 §3 (+ §1 tree) | AUDIT_03 §3 |
| §3.1 step 3 | Claimed File 8 already has lexicon upload field | Note field was missing; added in File 8 this pass | File 8 schema (pre-edit) |
| §3.1 step 4 | Asterisks grep cited AUDIT_01 §5 | → AUDIT_01 §4 Telephony | AUDIT_01 §4 |
| §5 | Claimed File 3 already has SSML fields; “File 9 Phase 4” | Deferred post–Phase 5; File 3 fields added as optional | File 9 phase list; File 3 |

---

## File 05 — `05_POST_CALL_INTELLIGENCE_AND_CRM_PIPELINE.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| Opening | “AUDIT_02 §1 scope note” | → AUDIT_02 scope note / preamble | AUDIT_02 preamble |
| §2 `CallRecording` | Quote “recordings are fetched…” cited §4 | Quote is §1; §4 is recording_url storage | AUDIT_02 §1, §4 |
| §4 dates | Claimed documented timezone gap in every legacy repo | Marked UCVE `[NEW]`; audits don’t document timezone anchoring | Grep of AUDIT_01–05 for timezone |
| §4 confidence | Overstrong Gladia confidence-field claim | Softened to match AUDIT_01 §5 wording | AUDIT_01 §5 |
| §5 provenance | Quote attributed to AUDIT_02 §2 | Exact phrase is AUDIT_02 §1 | AUDIT_02 §1 |

---

## File 06 — `06_MCP_SERVER_AND_REALTIME_RAG_SPEC.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| Opening | “five independent judgment calls” | → three voice-pipeline repos (awaazlabs chat/extraction only) | §1 table; AUDIT_01/03/04 §6 |
| §1 | Claimed all three forbid system-prompt concatenation | Habiba forbids; AUDIT_01 §6 lists concat as a possible hook — not UCVE guidance | AUDIT_01 §6; AUDIT_04 §1/§6 |
| §3.2 | “0.2s in three of four repos” | Align with File 1 Gladia vs LiveKit clarification | AUDIT_01/03/04 |

---

## File 07 — `07_TELEPHONY_AND_TRANSPORT_INFRASTRUCTURE.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §4.2 | “inbound only”; “no legacy repo implements outbound calling” | Habiba lists `outbound-calls` routes; AMD/warm-transfer/whisper remain `[NEW]` | AUDIT_04 §4 |
| §2 LiveKit table | Bare `metrics_updated` | Note legacy Habiba name → UCVE `metric` | File 8 §3; AUDIT_04 §4 |
| §5 | Event vocab pointed only at File 1 §3.4 | Explicit File 8 §3 names | File 8 §3 |

---

## File 08 — `08_UNIVERSAL_AGENT_BUILDER_AND_SDK_SPEC.md`

**Status:** Corrections applied.

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §1 schema | No pronunciation lexicon (File 4 claimed it) | Added `pronunciation_lexicon` | File 4 §3.1 |
| §1 schema | `toolConfig.description` optional vs File 3 required | `description` now required | File 3 `ToolDefinition` |
| §1 schema | No link to File 5 `CallDisposition` | Added optional `disposition_enum_ref` | File 5 §5 |
| §3 | Client→server `control.pong` / `client.interrupt_hint` prose-only | Added to TypeScript unions + layer note for Transcript vs wire vs `DiarizedTurn` | File 7 §3.2; File 3; File 5 |

**Otherwise clean:** §3 unification table matches AUDIT_01/03/04 catalogs; File numbering/title OK.

---

## File 09 — `09_DEVELOPER_IMPLEMENTATION_ROADMAP_AND_AUTONOMY_RULES.md`

**Status:** Minor correction applied (checklist targets fixed via File 2 renumbering).

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §5 #1 | Row text said “session init” only but also cited File 6 §2.2 (tool handlers) | Clarified row covers session-init **and** sync DB in async tools | File 2 §5.1; File 6 §2.2; AUDIT_04 §5 |
| §5 #1–#5 links | Pointed at File 2 §5.1–§5.4 which did not exist | Resolved by adding those subsections in File 2 | File 2 §5 post-edit |

**Otherwise clean:** Phase plan, Docker torch/numpy (AUDIT_03), Redis rate-limit (AUDIT_04 §5), CI harvest (AUDIT_04), event deferral to File 8 §3, and remaining anti-pattern link targets verified.

---

## Cross-cutting checks

| Check | Result |
|---|---|
| “File X of 9” headers / File 1 §6 index titles | Consistent after File 1 §5 tree pointer fix |
| Unified event vocabulary (`control.barge_in`, `control.hangup`, `metric`, …) | Normative UCVE sites updated; slash forms retained only in legacy provenance columns (File 8 §3 table) |
| Shared types (`Transcript`, `ToolDefinition`, `CallDisposition`) | Defaults/required fields aligned; layering documented in File 8 §3 |
| File 9 §5 anti-pattern “File where the fix is specified” | Links resolve after File 2 §5.1–§5.4 |

---

## Could not verify (pass 1 — resolved in pass 2)

Pass-1 flags 1–4 were all resolved against live trees. See **Pass 2** below.

---

## Summary counts (pass 1)

| Outcome | Count |
|---|---|
| Blueprint files needing corrections | **9 / 9** (all had at least one fix; File 09 was minor) |
| Blueprint files fully clean (zero edits) | **0** |
| Additional deliverable | `FINALIZATION_LOG.md` (this file) |

---

## Pass 2 — Live source spot-check (2026-08-17)

Trees: `legacy_codebases/`. Audit `file:line` cites from 2026-08-14 are **almost all still exact**. Material claim errors (not just missing cites) were corrected as follows.

### Previously unverifiable items — now confirmed

| Flag | Live finding | Where updated |
|---|---|---|
| `worker/config.py:60–76` RLS | CONFIRMED `set local role authenticated` at `:65` | File 1 §3.5 cite stands |
| `worker/tools.py:64,102` sync psycopg | CONFIRMED both `with psycopg.connect` inside `async def` | File 1 §3.2, File 6 §2.2 (path prefixed `worker/`) |
| `retail_prompt.md:10` asterisks | CONFIRMED | File 4 §3.1 |
| `retell-webhook/index.ts:280–289` no retry | CONFIRMED | File 5 §6 |
| `usage_events` | CONFIRMED table + `worker/usage.py` + `worker/main.py:365–381` | File 1 UsageMeter row |
| habiba outbound depth | **One-shot LiveKit-SIP dialer** (`telephony_service.py:999–1183`), not campaign CRUD; no AMD/warm-transfer | File 7 §4.2 |
| Gladia `confidence` | v3 dataclass has **no** field; MULTI declares it but never fills; habiba persist/SDK omit it | File 3 `Transcript`; File 9 #7 |

### File 01

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| Header | Trees now under `legacy_codebases/` | Noted | `origin/main` `3e9697a` |
| §2.2 UsageMeter | Abbreviated `usage.py` | Cite `worker/usage.py`, `usage_events` schema, shutdown emit | `worker/usage.py:1–8,23–58`; `worker/main.py:365–381`; `0001_schema.sql:58–65` |
| §3.2 | `tools.py` unqualified | → `worker/tools.py:64,102` | live file |
| §3.3 | `_hits` implied in mint | → `control_plane/app.py:62,238,262–269` | live file |

**Also confirmed (no text change):** Silero pool+Lock `vad_service.py:42–47`; JWT 120s `mint.py:28`; Gladia 0.2s both v3/MULTI; habiba `endpointing.min_delay=0.2` `main.py:197`.

### File 02

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §1.1 | `_SentenceBridge` lumped as STT→turn | Split: STT queue is `_transcript_queue` (v3 unbounded `:131`); SentenceBridge is LLM→TTS | v3 `gladia_service.py:131`, `websocket.py:33–36`; MULTI `session.py:25–27` |
| §5.2 | Only Groq sentence callbacks | Also Gladia `create_task` at `gladia_service.py:375–378` | live MULTI |
| §5.3 | Google key “at import” `:16` | Live request is `:75`; `:16` unused | `google_service.py:75` |
| §5.4 | MULTI “own Silero per session” | MULTI pools Silero; per-session cost is 3 TTS HTTP clients | `SileroModelPool`; `tts_manager.py:153–158` |

**Also confirmed:** barge-in drop of finals `websocket.py:271–273`; FSM apply-anyway `state_machine.py:45–51`; 700ms/0.3s verify; habiba interruption knobs `main.py:190–197`.

### File 03

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| `BaseVADProvider.feed` | Claimed v3 emits speech-start **and** speech-end | v3 returns True on **start only** (`silero_service.py:117–121`); UCVE still emits both | live V3 |
| `Transcript.confidence` | Soft “NOT VERIFIED” | Now: no field in v3; unused None in MULTI; absent in habiba | `gladia_service.py:63–70`; MULTI `interfaces.py:63–67`; habiba persist `main.py:336–338` |
| §6 URL keys | “at import time” | Cite live `:75` | `google_service.py:75` |

**Also confirmed:** CS defaults, CER comment `gladia.py:17–28`, registry no silent fallback, gemini-2.5-flash vs `gemini.py:10–24` remap, `/v1/voices` swallow `app.py:189–193`.

### File 04

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §2.2 `fallback_language` | Comment said unrecognized STT → `en` | Router **keeps current**; `en` is `LanguageRegistry.get()` only | `language_router.py:26–34`; `language_registry.py:133–136` |
| §2.3 `tts_first_chunk_word_count` | Implied YAML field | Hardcoded `groq_service.py:42–43`; YAML `chunk_min_words` is 10/12 | `ur.yaml`; `groq_service.py:42–43` |

**Also confirmed:** CS True in Gladia init not YAML; ur/ar 800ms; Deepgram adapter has no CS/LID kwargs.

### File 05

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §4 save-booking | “happily persist missing call_id” | ACK-without-persist `{result:"saved"}` | `save-booking/index.ts:15–16` |
| §4 timezone | Claimed unconstrained `[NEW]` | Appointment slots **are** clinic-zone; call events are UTC ISO | `appointment-time.ts`; `retell-webhook/index.ts:378–381` |
| §6 checkSecret | Implied one fail-open | Shared + VOB fail-open; CRM poc fail-closed | `_shared/supa.ts:23–27`; CRM `:281–285`; VOB `:215–217` |
| §6 idempotency row | “accepts records” | Same ACK-without-persist wording | `save-booking/index.ts:15–16` |

**Also confirmed:** events 36–61; forward 280–289; Green API `sendSmart`; recording proxy; silero/barge/pcm = 0 in app source; CRM Groq `llama-3.3-70b-versatile` (VOB default is `llama-3.1-8b-instant`).

### File 06

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §2.2 | `tools.py:64,102` | Confirmed live; path `worker/tools.py` | live habiba |

**Also confirmed:** FIXED_TOOLS, `_PERSONA_FRAME` isolation `worker/main.py:26–72`.

### File 07

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §3.1 SDK cite | `:264–311` as Room.connect | Connect is `:198–202`; 264–311 is event wiring | `sdk/src/index.ts` |
| §4.2 outbound | Route names only | Documented as one-shot LiveKit-SIP dialer; AMD/whisper/campaign still `[NEW]` | `telephony_service.py:999–1183`; grep AMD=0 |

### File 08

**Status:** Zero additional edits this pass. Event catalog, mint HMAC/120s TTL, `/v1/voices` swallow, persona isolation all confirmed live.

### File 09

| Section | What was wrong / missing | Change | Verified against |
|---|---|---|---|
| §5 #2 | “Unbounded queues \| v3, multilingual” | MULTI queues bounded; v3 unbounded; MULTI `ReplayableAsyncIterator._consumed` still unbounded per turn | File 2 §1.1 live check |
| §5 #5 | Implied MULTI Silero per session | Clarified v3 Silero+HTTP vs MULTI TTS HTTP | File 2 §5.4 |
| §5 #7 | “confidence field collected but never read” | v3 collects **language** unread; **confidence never collected** in any of four | v3 `GladiaTranscript`; habiba grep 0 |

### Pass 2 residual uncertainty

- Client jitter “~280ms” is the **in-file comment** assuming 4096-byte chunks; server yields ≥8192 so three real chunks ≈557ms. Blueprint still quotes the comment (File 1 §4) — not changed, flagged here.
- Nested `Agent-CRM-demo3` is a near-copy, not byte-identical; canonical CRM `types.ts` import has no `types.ts` on the canonical path (only nested). Out of blueprint scope.
- Deepgram plugin runtime LID (inside LiveKit plugin, not in-repo) remains unverified.

### Pass 2 summary counts

| Outcome | Count |
|---|---|
| Files with live-pass corrections | **8** (01–07, 09) |
| Files clean on live pass | **1** (File 08) |
| Previously unverifiable flags closed | **4 / 4** |

---

## Pass 3 — Product sovereignty (2026-08-17)

**Trigger:** explicit product mandate — standalone engine, IP kept local, cloud vendors interchangeable, no single throat to choke. Not an audit error; a policy layer on top of the harvest.

**Grounding:** File 3 already had `FailoverRouter` and habiba's registry; File 1 already had a raw WS plane; MULTI already failsover TTS. Legacy **defaults** were still single-vendor (v3 Gladia+Gemini+Uplift; habiba ur gladia+gemini+uplift; habiba orchestrator = LiveKit `AgentSession`, AUDIT_04 §6). This pass makes diversity a **startup/production rule**, not a future nicety.

| File | Change |
|---|---|
| 01 | Dual-plane rewrite: sovereign WS+SIP default; LiveKit optional media. New **§3.6** tiers 0–3 + kill-switch table. C4 adds local Whisper/Piper and dual trunks. Directory preview puts `worker-raw` first. |
| 02 | §3.2: SFU interruption knobs are adapter hints; FSM stays Tier 0. |
| 03 | Example chains require ≥2 routes including local ids; anti-pattern #4 single-vendor lists. |
| 04 | Acoustic layer not Gladia-only. |
| 05 | Extraction via FailoverRouter; pgvector default. |
| 06 | pgvector-in-Postgres default; Qdrant optional. |
| 07 | LiveKit plane optional; dual-home `SIPTrunkConfig`; outbound must not require `create_sip_participant`. |
| 08 | `providerConfig` `minItems: 2`; `sip_trunks`; SDK default native WS. |
| 09 | Phases 1–3 sovereign-first; compose as the product; anti-patterns #18–20; autonomy §6.2 sovereignty bullet. |

No `legacy_codebases/` edits. No monorepo scaffolding.

---

## Pass 4 — Product overview (2026-08-17)

Added `00_PRODUCT_OVERVIEW.md` (plain-English what/why/how we build, four packaging modes: product / service / SaaS / dedicated client, and a guide to files 01–09). Added `docs/blueprint/README.md`. File 1 reading order + index and File 9 header point at `00`. No engine code.
