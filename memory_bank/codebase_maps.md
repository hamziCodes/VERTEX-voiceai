# Codebase Maps — VERTEX_voiceai

> Bootstrap index. Full dossiers: `AUDIT_01`…`05`. Do not re-audit unless source changed.
> Disk names ≠ protocol aliases: `awaazlabs` (double-a); `AI_voice_agent_v3 - gemini` (space).

## Aliases
| Alias | Path |
|-------|------|
| V3 | `AI_voice_agent_v3 - gemini/` |
| AWAZ | `awaazlabs/` |
| MULTI | `Multilingual_AI_Voice_Agent_gittracked/` |
| HAB | `habiba-sdk-agent/` |

---

## 1. Repository Topologies

### V3 — Scratch Urdu PCM loop
```
AI_voice_agent_v3 - gemini/
├── backend/app/
│   ├── main.py                 # FastAPI entry, mounts WS
│   ├── config.py               # Settings (thresholds, models)
│   ├── transport/websocket.py  # /ws/audio, SessionOrchestrator, CallState
│   ├── services/
│   │   ├── silero_service.py   # VAD (torch.hub per session)
│   │   ├── gladia_service.py   # STT Live V2
│   │   ├── gemini_service.py   # LLM
│   │   └── uplift_service.py   # TTS HTTP stream
│   └── prompts/retail_prompt.md
├── frontend/index.html         # Mic 16k PCM → WS
├── requirements.txt / render.yaml
└── docs/ (blueprint stubs only)
```

### AWAZ — Dashboard + Retell CRM (NOT a voice engine)
```
awaazlabs/
├── ali-Awaazlabs-client-dashboard-backend/
│   └── supabase/functions/     # CANONICAL Edge Functions
│       ├── retell-webhook/     # call_* events
│       ├── transcript-crm-poc/ # Groq extraction
│       ├── support-chat/
│       └── _shared/{supa,messaging}.ts
├── Agent-CRM-demo3/            # DUPLICATE of Edge Functions — prefer ali-*
├── AwaazLabs-frontend-from-github/  # Next 15 + Clerk dashboard
└── customer-support-chat/      # Duplicate chat route
```
Grep voice PCM/Silero/VAD = **0**. Nested gits per subfolder.

### MULTI — Modular relative of V3
```
Multilingual_AI_Voice_Agent_gittracked/
├── backend/app/
│   ├── main.py
│   ├── orchestration/session.py
│   ├── core/
│   │   ├── interfaces.py       # Protocols (orchestrator still concrete)
│   │   ├── language_registry.py / language_router.py
│   │   └── config/languages/{en,ur,ar,ms}.yaml
│   ├── services/
│   │   ├── vad_service.py      # SileroModelPool + EnergyVAD + AdaptiveNoiseGate
│   │   ├── gladia_service.py
│   │   ├── groq_service.py
│   │   ├── tts_manager.py      # Uplift/Google/ElevenLabs + circuit breaker
│   │   └── prompt_builder.py
│   └── transport/websocket.py
├── frontend/app.js             # Clerk hard-bypassed
├── Dockerfile                  # python:3.11-slim
└── requirements.txt            # ⚠ no torch/numpy
```

### HAB — Multi-tenant VaaS (LiveKit Agents)
```
habiba-sdk-agent/
├── control_plane/app.py + mint.py   # POST /v1/session HMAC+JWT
├── worker/
│   ├── main.py                      # AgentSession + silero.VAD.load()
│   ├── tools.py                     # end_conversation_summary, escalate
│   └── providers/
│       ├── registry.py              # no silent fallback
│       ├── capabilities.py          # lang×provider matrix
│       └── stt|llm|tts/…
├── tenant_portal_api/telephony_routes.py
├── telephony/src/routes.ts          # Telnyx webhooks
├── sdk/src/index.ts                 # @awaazlabs-uva/voice
├── docker/*.Dockerfile
├── tests/ (60+), .github/workflows/ci.yml
└── docs/
```
Telephony = **Telnyx + LiveKit SIP**. Twilio/Asterisk = **ABSENT**.

---

## 2. Component Index

| Layer | V3 | MULTI | HAB | AWAZ |
|-------|----|-------|-----|------|
| **VAD** | `silero_service.py` — `SileroVAD`, thresh **0.55**, speech/silence **250ms**, win **512** | `vad_service.py` — `SileroModelPool`, `EnergyVADProcessor`, `AdaptiveNoiseGate` (k=3, win=50, floor=0.015); default thresh **0.5**, speech 250ms, silence UI 200ms; ur/ar YAML silence **800ms**; `vad_silence_commit_ms=600` **unused** | `silero.VAD.load()` no kwargs — thresholds **NOT VERIFIED** | ABSENT |
| **STT** | `gladia_service.py` — Gladia Live V2 `solaria-1`, langs `["ur","en"]`, `code_switching=True`, endpoint **0.2s** | same Gladia + `["ur","en","ar","ms"]`, CS true, endpoint 0.2 | `providers/stt/gladia.py` — **ur CS=False** (CER 0.14 vs 0.43); deepgram for en | ABSENT (Retell owns voice) |
| **LLM** | `gemini_service.py` — `gemini-3.1-flash-lite`, temp 0.7, max_tok 1000, hist last **6**, `[END_CALL]` | `groq_service.py` — `llama-3.1-8b-instant` (config) vs `.env.example` `llama3-8b-8192`; max_tok **150**; `prompt_builder.build_messages` | Gemini adapter remaps `2.5-flash`→`3.1-flash-lite`; groq in en only; persona via `_PERSONA_FRAME` | Groq `llama-3.3-70b-versatile` in `extraction.ts` (post-call text) |
| **TTS** | `uplift_service.py` — POST upliftai, `PCM_22050_16`, skip 2048B, align 8192, retries=1 | `tts_manager.py` — failover, first-chunk TO 3.5s / next 1.5s, CB 2 fails/60s | cartesia/elevenlabs/rime/uplift via registry | ABSENT |
| **WS / Session** | `transport/websocket.py` — `SessionOrchestrator`, `CallState`, `_barge_in()`, `AudioSender` | `orchestration/session.py` + WS `/ws/audio`; barge: pause→**700ms** verify→min sustain **0.3s** | LiveKit room via mint; interrupt `mode=adaptive`, false_int TO **0.7**, endpoint min_delay **0.2** | N/A |
| **Telephony** | ABSENT (docs stub `TELEPHONY_PROVIDER=twilio` only) | ABSENT | `telephony_routes.py`, `POST /webhooks/telephony/telnyx`, LiveKit SIP | Retell webhook only |
| **Auth** | WS **ABSENT**; REST `/` `/healthz` | Clerk **bypassed** in `frontend/app.js` | HMAC mint `tenant_id.ts.nonce.agent_id`, replay 60s, JWT TTL **120s**, rate 120/min **in-memory** | Clerk dashboard; Retell `checkSecret` **fail-open** if unset |

Key methods (harvest anchors):
- V3: `_barge_in()`, `AudioSender`, `SessionOrchestrator`
- MULTI: `LanguageRouter`, `SileroModelPool`, `tts_manager` circuit breaker
- HAB: `mint.py`, `registry.py`, `tools.py` (`end_conversation_summary`, `escalate_to_human`)
- AWAZ: `retell-webhook/index.ts`, `extraction.ts`

---

## 3. Dependency & Framework Matrix

| | V3 | MULTI | HAB | AWAZ |
|-|----|-------|-----|------|
| Runtime | Py **3.11.9** (render) | Py **3.11** Docker slim | Py **3.12** | Node (Next **15.5.20**, React **19.2.7**) |
| Web | FastAPI + WS | FastAPI + WS | LiveKit Agents **1.6.5** + FastAPI control plane | Next + Supabase Edge |
| Audio AI | torch (req `2.11.0+cpu`), Silero hub, Gladia, Gemini, Uplift | Gladia, Groq, multi-TTS; **torch/numpy MISSING from requirements** | livekit-plugins silero/gladia/… | Groq text only |
| Auth | none on WS | Clerk (disabled) | HMAC+JWT mint | Clerk **7.5.15** |
| Deploy | `render.yaml`, **no Dockerfile** | Dockerfile + Render WS URL | `docker/*.Dockerfile`, CI | Supabase + Vercel-style |
| Tests | sparse | sparse | **60+** in `tests/` | limited |

Collective ABSENT: MCP, RAG/vector cache, self-hosted SFU, Twilio/TwiML/Asterisk, Redis mint limiter, Vault/KMS, Stripe. Usage metering = **HAB only**.
