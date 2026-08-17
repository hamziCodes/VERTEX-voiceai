# What we are building — Unified Core Voice Engine (plain English)

**Start here.** The other nine files are the engineering blueprint. This file is the same story in English: what the product is, why it exists, how it is different, how we will build it, how it scales as a product / a service / SaaS / a dedicated client install, and what each technical document is for.

Codename: **Unified Core Voice Engine (UCVE).**  
Working name in this repo: VERTEX voice AI.

---

## 1. In one paragraph

We are building **our own voice-agent engine** — software that can listen to a person on a phone or in a browser, understand them (including Urdu and mixed Urdu/English), think, talk back quickly, use tools and knowledge, and after the call write a clean summary into a CRM. The hard parts of that loop (turn-taking, barge-in, language switching, provider failover, tenancy, post-call extraction) live **in our code**, as company IP. Big-tech APIs (speech-to-text, language models, text-to-speech, phone carriers, optional WebRTC) are **plug-in adapters**. If one vendor raises prices, blocks a region, or goes down, the engine keeps running on the next adapter or on a local fallback. We can sell this as a **multi-tenant SaaS**, run it as a **managed service**, or install it **for one client** on their machines.

That is the product. It is not a thin wrapper around LiveKit, Retell, Twilio, or Gladia.

---

## 2. Where this came from (so the blueprint is not fiction)

Four existing codebases were audited in August 2026. None of them *is* the product. Together they cover almost all of the pieces:

| Legacy tree (on disk: `legacy_codebases/`) | What it actually is | What we take from it |
|---|---|---|
| `AI_voice_agent_v3 - gemini` | A single-tenant browser voice loop for Urdu retail (Zara / Finova). No auth, no telephony, providers hardcoded. | The **barge-in lock** (cancel speech the instant the user talks), Silero VAD numbers, Uplift streaming TTS tricks, sentence chunker. |
| `Multilingual_AI_Voice_Agent_gittracked` | Same family of loop, but with language packs (en/ur/ar/ms), a language router, hybrid VAD, and TTS failover. | **Language router**, Silero **pool** + energy fallback, **TTS circuit breaker**, YAML language profiles. |
| `habiba-sdk-agent` | Closest to a real “voice as a service”: HMAC session mint, quotas, provider registry, LiveKit WebRTC, Telnyx phone numbers, a browser SDK. | **Control plane** (who is allowed to start a call), **registry** (no silent provider swap), tenancy, Telnyx patterns, SDK “zero secrets in the browser.” |
| `awaazlabs` | **Not a voice engine.** Clinic dashboard + Retell webhooks + Groq extraction + WhatsApp. | **After-the-call** extraction, validation, CRM/WhatsApp dispatch. We generalize it off dental/Retell. |

The five audit reports in `auit_docs/` are the evidence. The nine numbered blueprint files turn that evidence into one engine. `FINALIZATION_LOG.md` is the paper trail of every correction we made against the audits and the live trees.

---

## 3. How this is different

**Different from the four legacy apps.** Those were prototypes or adjacent products. v3 and multilingual cannot be sold as multi-tenant SaaS (no auth on the audio socket). Habiba can be sold as VaaS but the *conversation brain* is tied to LiveKit’s agent runtime — if LiveKit is blocked, the product is blocked. Awaazlabs never hears audio; Retell does. UCVE is one engine with one event language, one FSM, one provider registry, and two ways to move audio (our WebSocket, or an optional SFU).

**Different from “just use Retell / Vapi / Bland.”** Those companies *are* the orchestrator. You send them the prompt and the phone number; they own the loop. We own the loop. Vendors supply a skill (transcribe, generate, speak, carry a PSTN call). That is how we keep the architecture a company secret and how we stay standing if a vendor changes terms.

**Different from “just use LiveKit Agents.”** LiveKit is excellent *media* (WebRTC, jitter, SIP into a room). It is a poor place to hide our IP. Habiba already proved the trap: the audit says LiveKit `AgentSession` *is* the orchestrator and is hard to run without LiveKit. UCVE uses LiveKit, if at all, as an **optional media adapter**. Turn-taking, barge-in, language, tools, and RAG stay in `core/`.

**Different from a research demo.** The target is a shippable engine: bounded queues, fail-closed secrets, dual phone trunks, kill-switch tests, docker-compose as the default install, Kubernetes when you actually need it.

---

## 4. What the system does, end to end

1. A **browser, app, or phone call** connects.
2. We **mint a short-lived session** (HMAC from the customer’s backend, or our control plane). The browser never holds Gladia/Gemini keys.
3. Audio is normalized to 16 kHz PCM. **Silero VAD** (with an energy fallback) decides when the person started and stopped talking.
4. **Speech-to-text** turns speech into text (Gladia, Deepgram, or local Whisper — never only one).
5. A **language router** decides whether this was English, Urdu, Arabic, Malay, or a mix, without flipping language on a single noisy word.
6. An **LLM** replies, streaming. Optional **RAG** (facts from the tenant’s docs) and **MCP tools** (bookings, CRM, escalate to a human) inject as *data*, not as a rewritten system prompt — so a poisoned FAQ cannot hijack the agent.
7. A **chunker** splits the reply into speakable sentences; **TTS** starts on the first sentence (Uplift, ElevenLabs, Cartesia, or local Piper). If the user interrupts, we **barge in**: cancel LLM and TTS, flush the speaker queue, and listen again — including the words that caused the interrupt (v3 used to throw those away).
8. When the call ends we **extract structured fields**, verify them, summarize, and **webhook** the CRM / WhatsApp / whatever the tenant configured. Recordings and transcripts live in **our** database.

Latency target for “user stopped talking → first audio of the reply” is under ~450 ms on a good path; the honest cascaded range is wider, which is why we allow an optional speech-to-speech vendor path *and* why we fail over when a vendor is slow.

---

## 5. How we build it (without boiling the ocean)

We do **not** rebuild AWS. We do **not** start by wrapping LiveKit. Order is in File 9; in English:

| Phase | What you can demo when it is done |
|---|---|
| 1 — Core engine | Browser talks to **our** WebSocket. Turns and barge-in work. **LiveKit is not installed.** |
| 2 — Providers | Swap STT/LLM/TTS in config. Kill Gladia or Groq in a test; the call continues on Whisper / Gemini / Piper. |
| 3 — Telephony | A real phone number reaches the **same** engine. Second SIP trunk exists before we call it production. LiveKit SIP is optional. |
| 4 — Intelligence | Tenant docs retrieve mid-call; tools run; after the call a CRM payload goes out. |
| 5 — Studio & SDKs | A developer (or we, for a client) configures an agent in a UI and embeds a widget. |
| 6 — Harden | Latency traces, load on mint/admission, every anti-pattern in File 9 §5 actually gone. |

Default install: **Docker Compose** of control plane + sovereign worker + Postgres + Redis. Helm and Terraform exist for when a deployment is actually large. GPU (self-hosted LLM) is optional.

Implementation has **not** started. This folder is the blueprint. The four legacy trees stay read-only references under `legacy_codebases/`.

---

## 6. How it scales — four ways to sell the same engine

The same `core/` is the product. Packaging changes. That is how one codebase supports a company, not four forks.

### 6.1 As a **product** (the engine)

We ship UCVE: the loop, the registry, the studio schema, the SDKs. Customers (or our services team) run it. Scaling here means **horizontal workers** (more call capacity), **pooled VAD**, **Redis** for hot session state, **Postgres** for durable tenants/transcripts/usage. The bottleneck is calls, not “which vendor we wrapped.”

### 6.2 As a **service** (we operate it for you)

A clinic, a bank, or a retailer does not want Kubernetes. We run the compose/Helm stack, bring a phone number, tune Urdu, connect their CRM. They get an agent. We get an operations motion. Scaling here is **playbooks** (File 5 extraction schemas, File 8 agent config), not a new engine per client.

### 6.3 As **SaaS** (multi-tenant cloud)

Habiba already sketched this: many tenants, HMAC mint, quotas, RLS so tenant A cannot read tenant B’s agent. UCVE keeps that and applies it to the sovereign audio plane too (v3/multilingual had **no** auth on `/ws/audio` — that does not ship). Scaling here is **tenant isolation**, usage metering (`usage_events`), and the control plane in front of a pool of workers. One cluster, many customers, usage-based or seat-based billing later — billing productization was a gap in all four repos; metering is not.

### 6.4 As a **dedicated / client-specific** install

A bank or government client who will not send audio to our multi-tenant cloud gets **the same binaries** on their VPC or on-prem: local Whisper/Piper/Ollama, their Postgres, their SIP trunk, no LiveKit account required. We customize persona, tools, and extraction schema — not a fork of the engine. That is why Tier 0 IP must not live inside a vendor runtime, and why docker-compose is the first-class path.

These four are not four architectures. They are four **deployment contracts** on one architecture. If we violate that (a “SaaS-only LiveKit build” and a separate “on-prem Whisper fork”), we have failed the blueprint.

---

## 7. Independence rules (why we will not die with one vendor)

Stated fully in File 1 §3.6. In English:

- **Our brain never leaves the building.** VAD, barge-in, language, tools, prompts stay in our process.
- **Cloud is for when it is worth it.** Gladia may beat local Whisper on Urdu CER; Groq may beat Ollama on time-to-first-token. Then we *use* them — with a second name configured.
- **One name in the list is a bug.** Urdu STT cannot be “Gladia only.” Urdu TTS cannot be “Uplift only.” That is how the prototypes died if a key expired.
- **Kill switches.** If LiveKit, Gladia, Uplift, Groq, or Telnyx is blocked, a documented other path still places or continues a call.
- **Secrets.** Browser holds a publishable key only. Provider keys stay on the server. Webhooks fail closed if the shared secret is missing (awaazlabs fail-open is banned).

We are not trying to become Google. We are refusing to be a single API key with a website.

---

## 8. What each blueprint file is, what it means, and why it matters

Read this file, then File 9’s autonomy section, then File 1 §3.6, then the rest as needed. You do not need all nine open to explain the company; you need all nine to *build* without re-litigating decisions.

### File 01 — `01_SYSTEM_TOPOLOGY_AND_ARCHITECTURE.md`

**What it is:** The map of the whole system: who talks to whom, the two audio planes, control plane vs workers, C4 diagrams, latency budget, and the sovereignty tiers.

**What it means:** There is one engine. Audio may arrive as raw PCM over our WebSocket or (optionally) via an SFU. Both hit the same core. Redis is for hot state; Postgres is the source of truth.

**Why it matters:** Without this file, someone will “just use LiveKit Agents” and we will have rebuilt habiba. The kill-switch table lives here so every other file can point at one policy.

### File 02 — `02_CORE_AUDIO_ENGINE_AND_STATE_MACHINE.md`

**What it is:** How audio is buffered, how a call moves through states (listening → user speaking → thinking → agent speaking → barge-in), and the exact cancel-and-flush protocol when the user interrupts.

**What it means:** Voice products die on two bugs: talking over the user, and dropping the sentence that interrupted you. v3 had a strong lock but threw away the barge-in utterance. Multilingual waited 700 ms to avoid false interrupts. We keep both, as *our* FSM, not LiveKit’s.

**Why it matters:** This is the feel of the product. If File 2 is wrong, the rest is a chatbot with a speaker.

### File 03 — `03_PLUGGABLE_PROVIDER_ABSTRACTION.md`

**What it is:** The interfaces for VAD, STT, LLM, TTS, and optional speech-to-speech; the registry; the failover router (timeouts, retries, circuit breaker, latency demotion).

**What it means:** Application code never imports “Gladia” directly. It asks the registry for “STT for Urdu.” Config lists a **priority chain**. Local names (`faster_whisper`, `piper`, `ollama`) are first-class.

**Why it matters:** This is how we stay a product instead of a Gladia+Gemini+Uplift script (which is literally what v3 is). File 8’s agent builder only works if these types exist.

### File 04 — `04_MULTILINGUAL_AND_CODE_SWITCHING_ENGINE.md`

**What it is:** How we handle Urdu/English mixing, when to switch language, how we chunk sentences, and how we clean text before TTS (numbers, brand names, no leftover markdown asterisks).

**What it means:** Habiba measured that turning Gladia code-switching *on* for Urdu made errors much worse (CER 0.14 vs 0.43). v3 and multilingual left it on. We default **off** for Urdu, overridable per tenant, and we do not bet the acoustic layer on Gladia alone.

**Why it matters:** This is a regional product, not an English-only wrapper. Wrong defaults here sound broken to the first real caller.

### File 05 — `05_POST_CALL_INTELLIGENCE_AND_CRM_PIPELINE.md`

**What it is:** After hangup: recording, diarized transcript, schema-driven extraction, verification (phones, dates, CRM match), summary, webhooks, follow-ups, longitudinal memory, redaction/compliance.

**What it means:** Awaazlabs already does “call ended → Groq JSON → clinic CRM / WhatsApp,” but hardcoded to one vertical, Retell events, fail-open secrets, and no retry. We keep the *shape* and make the schema tenant-owned.

**Why it matters:** Enterprises buy outcomes (appointment booked, lead scored), not waveforms. Without File 5 we are a toy that talks.

### File 06 — `06_MCP_SERVER_AND_REALTIME_RAG_SPEC.md`

**What it is:** How the live agent uses tools (MCP) and retrieves knowledge mid-call; where that text is injected; fillers (“let me check…”) while a tool runs; pgvector as the default store.

**What it means:** None of the four repos had RAG or MCP. They *did* independently mark the injection point (right before the user turn, not glued into the system prompt). Habiba’s rule — tenant text is DATA — becomes our rule for retrieved docs and tool results, so prompt injection is harder.

**Why it matters:** This is how a voice agent answers “what’s my balance / policy / appointment” from *the client’s* systems without us hardcoding each client.

### File 07 — `07_TELEPHONY_AND_TRANSPORT_INFRASTRUCTURE.md`

**What it is:** Phone audio (μ-law, 8 kHz) vs our 16 kHz PCM; native WebSocket vs optional LiveKit; SIP trunks; outbound dialing; live supervisor listen/whisper; calling-window compliance.

**What it means:** Habiba’s phones are Telnyx + LiveKit SIP. That is one valid adapter. Production needs a **second trunk**, and outbound must work on our Direct SIP path so a LiveKit outage does not mean “we cannot dial.” Awaazlabs has no telephony at all (Retell does).

**Why it matters:** A voice company that only works in Chrome is a demo. A voice company that only works on Telnyx+LiveKit is a hostage.

### File 08 — `08_UNIVERSAL_AGENT_BUILDER_AND_SDK_SPEC.md`

**What it is:** The JSON schema of an agent (persona, languages, provider chains, tools, knowledge, telephony, compliance), the REST mint API, the realtime event names (`transcript`, `control.barge_in`, `metric`, …), and Python/TypeScript/Flutter SDK sketches.

**What it means:** Studio, API, and SDKs all speak one config and one event list. v3 said `{type:control, action:barge_in}`; habiba used LiveKit events. We unify so analytics and UIs do not fork per transport.

**Why it matters:** This is how we sell to developers and how we clone an agent for a new client without rewriting the engine. `minItems: 2` on provider lists encodes the sovereignty rule in the schema itself.

### File 09 — `09_DEVELOPER_IMPLEMENTATION_ROADMAP_AND_AUTONOMY_RULES.md`

**What it is:** Target folder tree, six build phases and their exit tests, latency harness, Docker/K8s notes, the anti-pattern checklist (bugs we must not copy from the legacy repos), and the “these docs are not holy scripture” rules.

**What it means:** Build in dependency order. Phase 1 is a talking WebSocket. LiveKit is not a Phase 1 gate. Cursor (or any implementer) may fix the blueprint when the code disagrees, except for safety and sovereignty rules.

**Why it matters:** Without this file, the next session starts scaffolding random folders and re-imports habiba’s lock-in. The checklist is how we do not ship v3’s unbounded queues, awaazlabs’ fail-open webhooks, or multilingual’s API key in a URL.

### Also in this folder

| File | Role |
|---|---|
| `00_PRODUCT_OVERVIEW.md` | This document — English orientation. |
| `FINALIZATION_LOG.md` | Every factual correction vs audits and live code. Not a product spec; an audit trail. |

The five `AUDIT_*.md` files live in `auit_docs/` (spelling of the folder is historical). They are evidence, not the product description.

---

## 9. What we are not building (yet, or ever, in this blueprint)

- A new Google-scale cloud, our own cell network, or a from-scratch WebRTC SFU on day one.
- A dental-only or Finova-only agent as the engine (those are **tenant configs**).
- Clerk as a required login for the voice path.
- Retell as the runtime.
- A second engine for “on-prem clients.”

---

## 10. How to talk about this to a client or investor

**One sentence:** We built the voice engine; vendors supply hearing, thinking, and speaking as replaceable parts; we can run it in our cloud, in yours, or as a service.

**Proof we are not vapor:** four production-shaped codebases already ran pieces of this (Urdu barge-in, four-language router, HMAC tenancy, Telnyx dial, clinic CRM extraction). The blueprint is the merge plus the independence rules those codebases were missing.

**Proof we can scale:** one core, four packaging modes (product / service / SaaS / dedicated), workers scaled on concurrent calls, Postgres for tenants, Redis for live turns, dual trunks and dual AI vendors so growth is not capped by one contract.

---

## 11. Suggested reading order

1. This file (`00`).
2. File 1 §1 and §3.6 (map + independence).
3. File 9 §2 and §6 (how we build; what must not be “creatively” dropped).
4. File 2 and File 3 if you are implementing the loop.
5. File 7 if you are implementing phones.
6. File 5 and File 6 if you are implementing “smart after and during the call.”
7. File 8 if you are implementing Studio/SDK.
8. File 4 whenever Urdu/Arabic/Malay behavior is the question.
9. `FINALIZATION_LOG.md` only when a citation looks wrong.

Then stop. Implementation is a later session; this folder is the contract for that session.
