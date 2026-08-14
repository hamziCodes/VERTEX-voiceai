# SYNTHESIS: Cross-Repo Feature Matrix & Unified Engine Roadmap

**Synthesis date:** 2026-08-14  
**Method:** Re-read `AUDIT_01`–`AUDIT_04` only. Cells cite those dossiers (section numbers), not a second pass over source.  
**On-disk names:** `AI_voice_agent_v3 - gemini` | `awaazlabs` (protocol said `awazlabs`) | `Multilingual_AI_Voice_Agent_gittracked` | `habiba-sdk-agent`

## 1. Feature Comparison Matrix

| Feature | v3 gemini (`AUDIT_01`) | awaazlabs (`AUDIT_02`) | Multilingual (`AUDIT_03`) | habiba-sdk-agent (`AUDIT_04`) |
|---|---|---|---|---|
| **Language(s) supported** | Urdu + English STT (`["ur","en"]`); LLM output locked to Urdu script. AUDIT_01 §2 STT/LLM | Clinic EN/ES support chat; Retell voice language is vendor-side. AUDIT_02 §2 LLM, §5 | en, ur, ar, ms via YAML registry + Gladia 4-lang list. AUDIT_03 §2 STT, language YAML | `ur` and `en` capability table only. AUDIT_04 §2 STT/LLM/TTS |
| **Code-switching capability** | Gladia `code_switching=True` ur+en. AUDIT_01 §2 STT | **NOT IMPLEMENTED / ABSENT** in-repo (Retell). AUDIT_02 §2 STT | Gladia CS true + `LanguageRouter` debounce. AUDIT_03 §2 STT, §3 language | Urdu Gladia **CS explicitly False**. AUDIT_04 §2 VAD/STT, §5 |
| **VAD engine & quality** | Silero torch-hub; threshold 0.55; 250/250 ms; per-session model load. AUDIT_01 §2 VAD | **NOT IMPLEMENTED / ABSENT** (grep 0). AUDIT_02 §2 VAD | Silero pool + Energy RMS fallback + adaptive noise gate; unused `vad_silence_commit_ms`. AUDIT_03 §2 VAD | `silero.VAD.load()` no kwargs; numeric thresholds **NOT VERIFIED**. AUDIT_04 §2 VAD |
| **Barge-in support** | Full custom: interrupt event, cancel LLM/TTS, flush sender, `{control:barge_in}`. AUDIT_01 §3 barge-in | **NOT IMPLEMENTED / ABSENT**. AUDIT_02 §3 barge-in | VAD 700 ms verify + pause/resume + text backup >3 words. AUDIT_03 §3 barge-in | LiveKit adaptive interruption; `false_interruption_timeout=0.7`; `resume_false_interruption=False`. AUDIT_04 §3 barge-in |
| **Turn-taking sophistication** | FSM LISTENING/THINKING/SPEAKING; `_speaking_until` watermark; Gladia endpointing 0.2 s. AUDIT_01 §2–3 | **NOT IMPLEMENTED / ABSENT**. AUDIT_02 §3 state | FSM + comfort filler + verification window + language-specific 800 ms silence YAML. AUDIT_03 §2–3 | LiveKit `endpointing.min_delay=0.2` + adaptive detector. AUDIT_04 §2 VAD, §3 |
| **STT provider(s)** | Gladia Live V2 `solaria-1` only. AUDIT_01 §2 STT | **NOT IMPLEMENTED / ABSENT** in-repo; Retell transcripts ingested. AUDIT_02 §2 STT | Gladia Live V2 `solaria-1` only. AUDIT_03 §2 STT | Registry: gladia, deepgram; soniox adapter not in capabilities. AUDIT_04 §2 STT |
| **LLM provider(s)** | Gemini `gemini-3.1-flash-lite`; no tools. AUDIT_01 §2 LLM | Groq `llama-3.3-70b-versatile` for chat/extraction only (not voice). AUDIT_02 §2 LLM | Groq `llama-3.1-8b-instant` (env.example differs). AUDIT_03 §2 LLM | gemini + groq (en); groq absent for ur. Tools implemented. AUDIT_04 §2 LLM |
| **TTS provider(s)** | Uplift HTTP PCM_22050_16 only. AUDIT_01 §2 TTS | **NOT IMPLEMENTED / ABSENT**. AUDIT_02 §2 TTS | Uplift / Google / ElevenLabs + failover/circuit breaker. AUDIT_03 §2 TTS | uplift (ur); cartesia/elevenlabs/rime enabled, fish_audio testing (en). AUDIT_04 §2 TTS |
| **Transport (WebSocket/WebRTC/SIP)** | FastAPI binary PCM WebSocket `/ws/audio`. WebRTC **ABSENT**. AUDIT_01 §2 transport, §4 | Voice WS **ABSENT**. HTTP webhooks only. AUDIT_02 §2 transport, §4 WS | FastAPI `/ws/audio` PCM. WebRTC/SIP **ABSENT**. AUDIT_03 §2 transport, §4 | LiveKit WebRTC + LiveKit SIP; custom `/ws/audio` **ABSENT**. AUDIT_04 §2 transport, §4 |
| **Telephony support** | **NOT IMPLEMENTED / ABSENT**. AUDIT_01 §4 telephony | Retell call webhooks + recording URLs; no SIP/TwiML. AUDIT_02 §4 telephony | **NOT IMPLEMENTED / ABSENT**. AUDIT_03 §4 telephony | Telnyx + LiveKit SIP; Twilio/Asterisk **ABSENT**. AUDIT_04 §1 note, §4 telephony |
| **Session persistence** | In-process Gemini history only. AUDIT_01 §3 state | Supabase `bookings` / chat sessions. AUDIT_02 §3 state | In-process Groq history. AUDIT_03 §3 state | Postgres `sessions` + transcript JSONB + quota. AUDIT_04 §3 state |
| **Multi-tenancy support** | **NOT IMPLEMENTED / ABSENT**. AUDIT_01 §5 concurrency | Clerk org + clinic locations (ops CRM, not voice engine). AUDIT_02 §3 handshake, §5 concurrency | **NOT IMPLEMENTED / ABSENT**. AUDIT_03 §5 concurrency | HMAC tenants, RLS agent load, quota caps. AUDIT_04 §3 handshake/state, §5 concurrency |
| **Auth mechanism** | **NOT IMPLEMENTED / ABSENT** on WS. AUDIT_01 §3 handshake | Clerk middleware; dashboard-api shared secret; Retell `?s=` (fail-open if unset). AUDIT_02 §3 handshake, §4, §6 | Clerk **bypassed**; WS unauthenticated. AUDIT_03 §3 handshake | Host HMAC mint + LiveKit JWT; browser zero secrets. AUDIT_04 §3 handshake, §4 |
| **Config system (env/yaml/hardcoded)** | pydantic-settings `.env`; many hardcoded (greeting, Uplift URL, temp). AUDIT_01 §2, §6 | Env secrets + Deno.env; hardcoded FORM_BASE_URL / doctor. AUDIT_02 §6 | pydantic-settings + YAML language profiles; some unused keys. AUDIT_03 §2, §6 | `.env.local` + DB agent/provider fields + capabilities.py. AUDIT_04 §2, §3 |
| **Retry/resilience logic** | TTS only (`max_retries=1`); STT/LLM **ABSENT**. AUDIT_01 §2 TTS, §6 | Groq/Retell forward **no retry**. AUDIT_02 §5–6 | TTS failover 3.5/1.5 s + 60 s circuit breaker; STT/LLM **ABSENT**. AUDIT_03 §2 TTS, §5–6 | LiveKit plugins + mint rollback on dispatch fail; mint in-memory rate limit. AUDIT_04 §3 handshake, §5 |
| **Observability/logging** | Rotating app.log, vad_frames.log, per-session files; WS latency metrics. AUDIT_01 §1 tree, §4 WS | `console.error` / Edge logs; dashboard stats resources. AUDIT_02 §4 dashboard-api | Rotating app.log + per-session files + WS metrics; console filter. AUDIT_03 §1 main.py, §4 WS | loguru/LiveKit logs; Sentry optional; usage_events; admin usage endpoints. AUDIT_04 §2 libs, §4 admin, §5 |
| **Test coverage** | Present: `backend/tests/` live-API scripts. AUDIT_01 §1 tree | Essentially **ABSENT** except `appointment-time_test.ts`. AUDIT_02 §6 | Present: barge-in, arabic, replayable iterator, pipelines. AUDIT_03 §1, §6 | Present: `tests/` 60+ modules + CI pytest. AUDIT_04 §1 tree, §6, `.github/workflows/ci.yml` |
| **RAG/MCP readiness** | **ABSENT**; inject at `generate_reply` contents. Score distance high. AUDIT_01 §6 RAG | **ABSENT** for voice; chat messages array only. AUDIT_02 §6 RAG | **ABSENT**; `build_messages` injection point. AUDIT_03 §6 RAG | **ABSENT**; `FIXED_TOOLS` / `chat_ctx` injection. AUDIT_04 §6 RAG |
| **Modularity score (from per-repo audits)** | **3/10**. AUDIT_01 §6 | **5/10**. AUDIT_02 §6 | **7/10**. AUDIT_03 §6 | **8/10**. AUDIT_04 §6 |
| **Deployment method (Docker/bare/serverless)** | Render `render.yaml` + uvicorn; **no Dockerfile**. AUDIT_01 §1, §2 | Vercel Next.js + Supabase Edge Functions. AUDIT_02 §1, §2 | Dockerfile python:3.11-slim + Render URL in frontend. AUDIT_03 §1 Dockerfile, §2 | `docker/*.Dockerfile` Python 3.12 + GitHub Actions deploy. AUDIT_04 §1, §2 |

## 2. Best-of-Breed Component Harvest

### VAD

- **Component:** Dual-engine VAD (Silero pool + Energy RMS + adaptive noise gate) with language-specific silence overrides
- **Source:** `Multilingual_AI_Voice_Agent_gittracked/backend/app/services/vad/vad_service.py`
- **Why it's best-of-breed:** AUDIT_03 §2 documents Silero checkout pool, Energy fallback, `AdaptiveNoiseGate`, and YAML 800 ms ur/ar silence — more complete than v3’s per-session `torch.hub.load` (AUDIT_01 §2, §5 memory) or habiba’s opaque `VAD.load()` (AUDIT_04 §2).
- **Porting note:** Cut FastAPI session construction; torch/numpy are **undeclared** in multilingual `requirements.txt` (AUDIT_03 §2, §6). Habiba already depends on `livekit-plugins-silero` — prefer exposing thresholds rather than duplicating two Silero stacks.

- **Component:** Tuned barge-in hysteresis constants (threshold 0.55, 250/250 ms, speech-start-only trigger)
- **Source:** `AI_voice_agent_v3 - gemini/backend/app/services/silero_service.py` + `backend/app/core/config/config.py`
- **Why it's best-of-breed:** AUDIT_01 §2 lists explicit, cited numbers (unlike habiba’s **NOT VERIFIED** plugin defaults).
- **Porting note:** Coupled to per-orchestrator model load (AUDIT_01 §5 blocking). Use multilingual pool pattern.

### STT

- **Component:** Gladia Live V2 init with explicit language lists and CS flag
- **Source:** `AI_voice_agent_v3 - gemini/backend/app/services/gladia_service.py` (ur+en CS on); `Multilingual_AI_Voice_Agent_gittracked/backend/app/services/stt/gladia_service.py` (4 langs CS on); `habiba-sdk-agent/worker/providers/stt/gladia.py` (single language, CS off with CER rationale)
- **Why it's best-of-breed:** Habiba adapter is the only one that **documents a measured CER tradeoff** for disabling CS (AUDIT_04 §2, §5). Multilingual is the only in-repo 4-language streaming config (AUDIT_03 §2).
- **Porting note:** Unify behind habiba `registry.py` so CS is a capability flag, not a hardcoded True/False.

### LLM orchestration

- **Component:** Language-profile sentence chunker + ephemeral directive injection
- **Source:** `Multilingual_AI_Voice_Agent_gittracked/backend/app/services/llm/groq_service.py` + `prompt_builder.py` + `backend/app/core/config/languages/*.yaml`
- **Why it's best-of-breed:** AUDIT_03 §2–3: per-language delimiters, first-chunk 2-word TTFT override, directive placed immediately before user turn — more portable than v3’s Gemini-only regex (AUDIT_01 §2).
- **Porting note:** Orchestrator still instantiates `GroqService` concretely (AUDIT_03 §6). Wrap as habiba-style adapter.

- **Component:** Untrusted-tenant persona isolation + fixed tools
- **Source:** `habiba-sdk-agent/worker/main.py` (`SYSTEM_INSTRUCTIONS`, `_PERSONA_FRAME`) + `habiba-sdk-agent/worker/tools.py`
- **Why it's best-of-breed:** AUDIT_04 §1, §2 LLM, §6: only repo with tool-calling and prompt-injection framing for multi-tenant prompts.
- **Porting note:** Tools currently do sync psycopg inside `async def` (AUDIT_04 §5 blocking).

- **Component:** Urdu retail persona + `[END_CALL]` protocol
- **Source:** `AI_voice_agent_v3 - gemini/backend/app/core/prompts/retail_prompt.md` (also multilingual `base_system_prompt.md`)
- **Why it's best-of-breed:** AUDIT_01 §2–3: explicit TTS format, injection defense, termination tag wired to WS close.
- **Porting note:** Hardcoded Finova/Zara; belongs in tenant prompt slot (habiba pattern), not engine code.

### TTS

- **Component:** `TTSManager` failover + circuit breaker + replayable iterator
- **Source:** `Multilingual_AI_Voice_Agent_gittracked/backend/app/services/tts/tts_manager.py`
- **Why it's best-of-breed:** AUDIT_03 §2 TTS: 3.5 s first-chunk / 1.5 s subsequent timeouts, 2-failure/60 s breaker, language-aware fallbacks — habiba registry selects providers but has no in-repo failover wrapper (AUDIT_04 §2).
- **Porting note:** Constructs three HTTP clients per session (AUDIT_03 §5 memory). Warm at worker process, not per room.

- **Component:** Uplift streaming + pop-trim + even-byte align + retry
- **Source:** `AI_voice_agent_v3 - gemini/backend/app/services/uplift_service.py` (and multilingual copy)
- **Why it's best-of-breed:** AUDIT_01 §2 TTS: only in-house HTTP streaming implementation with cited timeouts/retries (habiba uses LiveKit plugin).
- **Porting note:** Hardcoded `https://api.upliftai.org/v1/synthesis/text-to-speech` (AUDIT_01 §6).

### Transport

- **Component:** Bounded PCM queues + `ws_lock` + sender interrupt drop
- **Source:** `AI_voice_agent_v3 - gemini/backend/app/transport/{audio_receiver.py,audio_sender.py,websocket.py}`
- **Why it's best-of-breed:** AUDIT_01 §3–5: drop-oldest inbound, backpressure outbound, shared interrupt with send-loop — required if unified engine keeps a raw-PCM WS path alongside WebRTC.
- **Porting note:** No auth, unbounded `ConnectionManager` (AUDIT_01 §3, §5).

- **Component:** Zero-secret LiveKit browser SDK
- **Source:** `habiba-sdk-agent/sdk/src/index.ts` (`@awaazlabs-uva/voice`)
- **Why it's best-of-breed:** AUDIT_04 §2 transport, §4 events: only production WebRTC client contract.
- **Porting note:** Depends on host HMAC backend + LiveKit Cloud (AUDIT_04 §3 handshake).

### Session management

- **Component:** HMAC mint, 60 s replay, quota, explicit agent dispatch
- **Source:** `habiba-sdk-agent/control_plane/mint.py` + `habiba-sdk-agent/control_plane/app.py`
- **Why it's best-of-breed:** AUDIT_04 §3–4: only multi-tenant admission control; others unbounded (AUDIT_01/03 §5).
- **Porting note:** Rate limiter is in-process dict — not multi-replica (AUDIT_04 §5).

- **Component:** Language router debounce
- **Source:** `Multilingual_AI_Voice_Agent_gittracked/backend/app/orchestration/language_router.py`
- **Why it's best-of-breed:** AUDIT_03 §3: 3-word immediate switch vs 2-in-a-row for short utterances — neither v3 nor habiba has this (habiba disables CS).
- **Porting note:** Requires STT `language` on finals (Gladia Transcript in AUDIT_03 §2).

### Telephony

- **Component:** Telnyx machine API + SIP participant resolve + webhooks
- **Source:** `habiba-sdk-agent/tenant_portal_api/telephony_routes.py`, `telephony_webhooks.py`, `worker/telephony_runtime.py`, `telephony/src/routes.ts`
- **Why it's best-of-breed:** AUDIT_04 §4: only real PSTN path. awaazlabs is Retell-post-call CRM (AUDIT_02 §4), not a trunk.
- **Porting note:** Not Twilio/Asterisk (AUDIT_04 header). Worker metadata resolve falls back to participant JWT (AUDIT_04 §3).

- **Component:** Retell post-call CRM extraction + WhatsApp Green API
- **Source:** `awaazlabs/ali-Awaazlabs-client-dashboard-backend/supabase/functions/retell-webhook/index.ts` + `transcript-crm-poc/` + `_shared/messaging.ts`
- **Why it's best-of-breed:** AUDIT_02 §3–4: only structured post-call booking/VOB pipeline. Complementary to live engine, not a substitute.
- **Porting note:** Fail-open `checkSecret` (AUDIT_02 §6). Nested function duplicates.

## 3. Architectural Gap Analysis

Checked across all four audits. If a capability exists in even one repo, it is not listed as a collective gap.

### Collectively ABSENT (checked, not found in any of the four)

| Gap | How it was checked |
|---|---|
| **MCP integration** | AUDIT_01 §6, AUDIT_02 §6, AUDIT_03 §6, AUDIT_04 §6 all **NOT IMPLEMENTED / ABSENT**. |
| **Real-time RAG / dynamic RAG cache** | Same four §6 RAG sections: no retriever, no cache, no vector store in voice path. awaazlabs `knowledge` UI is not retrieval (AUDIT_02 §6). |
| **Self-hosted WebRTC SFU** | AUDIT_01/03 WebRTC **ABSENT**. AUDIT_02 WebRTC **ABSENT**. AUDIT_04 uses **LiveKit Cloud** URL/JWT, not an in-repo SFU. |
| **Twilio Media Streams / TwiML / Asterisk** | AUDIT_01 §4 telephony ABSENT; AUDIT_02 TwiML/SIP ABSENT; AUDIT_03 telephony ABSENT; AUDIT_04 Twilio/Asterisk grep 0. |
| **Distributed session store / Redis** | AUDIT_01/03 in-process history only. AUDIT_02/04 use Postgres but AUDIT_04 §5 documents mint rate-limit as **in-memory `_hits`**, not a shared cache. No Redis mentioned in any §2 stack table. |
| **Horizontal scaling strategy for the mint/admission plane** | AUDIT_04 §5: in-process 120/min limiter. AUDIT_01/03 unbounded ConnectionManager. No shared lease/lock service. |
| **Secrets manager (Vault/KMS rotation as a service)** | All use env files / Clerk / HMAC hashes in DB (AUDIT_04 `secrets.py`/`secrets_db.py`). No Vault/AWS SM client in §2 inventories. |
| **Billing/usage metering (except habiba’s new path)** | AUDIT_01–03: no usage_events. Habiba **does** emit `usage_events` (AUDIT_04 §3 shutdown) — so **usage metering is not a four-repo gap**. Stripe/customer invoices: **NOT IMPLEMENTED / ABSENT** in all four (no payment-provider rows in any §2 table). |
| **Real-time analytics product** | Per-turn WS metrics exist in AUDIT_01/03 §4; habiba SDK `metrics_updated` passthrough AUDIT_04 §4; awaazlabs dashboard stats AUDIT_02 §4. None is a streaming analytics pipeline (ClickHouse/Kafka/etc.) — **ABSENT** as a platform. |
| **Multi-tenant isolation of the PCM loop** | Habiba isolates LiveKit jobs + RLS (AUDIT_04). v3/multilingual have none (AUDIT_01/03 §5). Unified engine still must build isolation for any non-LiveKit PCM path. |
| **CI/CD for repos 1–3** | AUDIT_04 has `.github/workflows`. AUDIT_01 Render yaml only; AUDIT_02 Vercel implied; AUDIT_03 Dockerfile. In-repo CI workflows for 01–03: **NOT IMPLEMENTED / ABSENT** (not listed in those trees). |
| **Production test coverage for 01–02** | AUDIT_02 tests essentially absent; AUDIT_01 live scripts only; AUDIT_03/04 have suites. Unified engine cannot inherit a shared test harness from all four. |

### Present in one place only (must be ported, not invented)

- Dual transport WebRTC + SIP: **habiba only** (AUDIT_04).
- Provider hot-swap registry: **habiba** (STT/LLM/TTS) + **multilingual** (TTS/language YAML) (AUDIT_03–04).
- Custom PCM barge-in: **v3 + multilingual** (AUDIT_01/03).
- Clinic CRM / Retell ops: **awaazlabs only** (AUDIT_02).
- Quota + HMAC VaaS control plane: **habiba only** (AUDIT_04).

### Unified-engine implication (judgment, not a claim of existing code)

North Star needs: habiba’s tenancy/transport/registry **plus** multilingual VAD/language router/TTS failover **plus** v3’s explicit barge-in lock protocol for a raw-PCM path **plus** new work for MCP, RAG cache, distributed admission, and billing productization. awaazlabs is an adjacent CRM shell, not a voice-core donor except post-call extraction patterns.
