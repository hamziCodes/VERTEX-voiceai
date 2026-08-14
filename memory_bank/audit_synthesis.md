# Audit Synthesis — Harvest + Debt + Scorecard

> Source: `AUDIT_01`…`05` (2026-08-14). Evidence-only; no re-audit.

## 1. Per-Project Strengths & Assets (HARVEST)

### V3 — `AI_voice_agent_v3 - gemini`
| Asset | Location / Spec |
|-------|-----------------|
| Barge-in interrupt | `websocket.py` `_barge_in()` — cancel LLM/TTS, flush queue, `{type:control,action:barge_in}` |
| Shared interrupt Event | `AudioSender` + orchestrator |
| VAD hysteresis numbers | thresh **0.55**, min speech/silence **250ms**, window **512** |
| Uplift HTTP stream pattern | `uplift_service.py` — skip 2048B pop, align 8192, `PCM_22050_16` |
| Mic framing | frontend 16 kHz PCM-16LE, **512 samples / 32 ms** |
| End-call tag | `[END_CALL]` in Gemini path + `retail_prompt.md` (Zara/Finova) |
| WS lock / PCM queues | transport layer patterns |

**Gap to fix if porting:** finals during `_speaking_until` dropped → barge utterance not next turn.

### MULTI — `Multilingual_AI_Voice_Agent_gittracked`
| Asset | Location / Spec |
|-------|-----------------|
| Hybrid VAD | `vad_service.py`: `SileroModelPool` + `EnergyVADProcessor` + `AdaptiveNoiseGate` (k=**3.0**, win=**50**, floor=**0.015**) |
| Language pack | YAML `languages/{en,ur,ar,ms}.yaml`; `LanguageRegistry` |
| Code-switch router | `LanguageRouter` — short utt needs **2** consecutive detections; **3+** words → immediate switch |
| Verified barge-in | pause sender → **700 ms** verify → min sustain **0.3 s** → barge or resume; text backup if final word_count > **3** |
| TTS failover | `tts_manager.py` — TO 3.5s/1.5s; circuit breaker **2** fails / **60 s** |
| Prompt injection | `prompt_builder.build_messages` — language directive before user |
| Interfaces stub | `core/interfaces.py` (orchestrator still concrete Gladia+Groq) |

### HAB — `habiba-sdk-agent`
| Asset | Location / Spec |
|-------|-----------------|
| Multi-tenant mint | `control_plane/mint.py` — HMAC `tenant_id.ts.nonce.agent_id`, replay **60s**, JWT TTL **120s** |
| Explicit agent dispatch | `POST /v1/session` → LiveKit |
| Provider registry | `worker/providers/registry.py` — **no silent fallback** |
| Capability matrix | `capabilities.py` — ur: gladia+gemini+uplift; en: gladia/deepgram, gemini/groq, cartesia/elevenlabs/rime |
| Gladia CER rationale | `stt/gladia.py` — **ur `code_switching=False`** (0.14 vs 0.43) |
| Persona isolation | `_PERSONA_FRAME` chat_ctx — never concat into `SYSTEM_INSTRUCTIONS` |
| Tools | `tools.py`: `end_conversation_summary`, `escalate_to_human` |
| Client SDK | `sdk/` `@awaazlabs-uva/voice` 0.1.0 + `livekit-client ^2.0.0` |
| Telephony | Telnyx webhook + LiveKit SIP (`telephony_routes.py`, `telephony/src/routes.ts`) |
| Interrupt policy | adaptive, `false_interruption_timeout=0.7`, `resume_false_interruption=False`, endpoint `min_delay=0.2` |
| Quota / JSONB transcript | shutdown persistence + `usage_events` |
| Test/CI depth | `tests/` 60+, `.github/workflows/ci.yml` |

### AWAZ — `awaazlabs` (adjacent CRM, not voice core)
| Asset | Location / Spec |
|-------|-----------------|
| Retell lifecycle | `retell-webhook/index.ts` — `call_started\|transcript_updated\|call_ended\|call_analyzed` |
| Schema extraction | `transcript-crm-poc/extraction.ts` — Groq `llama-3.3-70b-versatile` |
| WhatsApp notify | `_shared/messaging.ts` Green API |
| Dashboard UX | Next+Clerk tenant CRM UI |

---

## 2. Critical Technical Debt & Vulnerabilities

| ID | Severity | Project | Issue |
|----|----------|---------|-------|
| D1 | HIGH | V3 | `torch.hub.load` **per session** blocks event loop at VAD construct |
| D2 | HIGH | V3 | Unbounded `_transcript_queue` / `_SentenceBridge` — memory growth |
| D3 | HIGH | V3 | No WS auth; no session cap |
| D4 | MED | V3 | Barge finals ignored during `_speaking_until` |
| D5 | HIGH | MULTI | `requirements.txt` **missing torch/numpy** — Docker Silero may fail |
| D6 | HIGH | MULTI | Rejects WS if Silero unhealthy despite Energy fallback |
| D7 | MED | MULTI | `vad_silence_commit_ms=600` defined but **unused** |
| D8 | MED | MULTI | Clerk hard-bypassed (`initClerk`) |
| D9 | HIGH | HAB | Sync `psycopg.connect` inside `async def` tools — **blocks event loop** |
| D10 | MED | HAB | Rate limiter `_hits` **in-memory** — not multi-instance safe |
| D11 | MED | HAB | Gemini model remap vs capabilities list drift (`2.5-flash`→`3.1-flash-lite`) |
| D12 | HIGH | AWAZ | `checkSecret` **fail-open** if `RETELL_SHARED_SECRET` unset |
| D13 | HIGH | AWAZ | Dashboard proxy trusts client `x-role`/`x-actor` (recording route OK via Clerk) |
| D14 | LOW | ALL | No MCP, RAG, Redis mint, Vault/KMS, Twilio, self-hosted SFU |

Race / reconnect notes:
- V3/MULTI: WS reconnect handling incomplete (audit: unhandled reconnection paths).
- HAB: LiveKit handles transport; control-plane mint replay window 60s is the auth race surface.

---

## 3. Comparative Scorecard

| Dimension | V3 | MULTI | HAB | AWAZ |
|-----------|----|-------|-----|------|
| Latency path | Good (simple cascade) | Good + TTS failover cost | LiveKit overhead; SDK-tuned | N/A (HTTP post-call) |
| VAD accuracy | Solid Silero hysteresis | **Best** hybrid + noise gate | Silero defaults unverified | N/A |
| Modularity | **3/10** | **7/10** | **8/10** | **5/10** (CRM only) |
| Transport | Native WS PCM | Native WS PCM | **LiveKit WebRTC** + SIP | Retell black-box |
| Multilingual | ur+en CS | **ur/en/ar/ms** + router | Capability matrix; ur CS off | N/A |
| Multi-tenant | No | No | **Yes** (mint/quota) | Dashboard tenants |
| Telephony | Absent | Absent | **Telnyx+SIP** | Retell |
| Post-call CRM | Absent | Absent | Tools + transcript JSONB | **Best** Retell+Groq |
| Test/CI | Weak | Weak | **Strong** | Weak |
| Production readiness | Prototype | Near-prod (Docker gap) | **Closest to VaaS** | Prod dashboard |

### Best-of-breed map (unified engine)
```
VAD        ← MULTI vad_service + V3 hysteresis numbers
STT        ← HAB gladia adapter (CER) + MULTI 4-lang config
LLM        ← MULTI chunker/prompt_builder + HAB persona + tools
TTS        ← MULTI tts_manager failover + V3 uplift stream
Transport  ← HAB LiveKit SDK + V3/MULTI PCM WS queues
Session    ← HAB mint/quota + MULTI language_router
Telephony  ← HAB Telnyx/SIP
Post-call  ← AWAZ Retell CRM patterns (adapt to own transcripts)
```
