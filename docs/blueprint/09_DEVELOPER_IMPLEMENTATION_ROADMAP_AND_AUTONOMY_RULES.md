# 09 — Developer Implementation Roadmap & Autonomy Rules

File 9 of 9 — the last file to read, and the one that governs how the previous eight get built.

---

## 1. Target Monorepo Directory Structure

```text
unified-core-voice-engine/
├── README.md
├── docs/
│   ├── blueprint/                          # this 9-file suite, versioned alongside code
│   └── audits/                             # AUDIT_01–05, kept as permanent provenance record
├── control-plane/                          # habiba control_plane/ pattern, AUDIT_04 §1
│   ├── mint.py
│   ├── app.py
│   ├── secrets.py
│   └── tests/
├── worker-raw/                             # Sovereign cascaded worker (File 1 §3.6)
│   ├── main.py
│   ├── orchestration/
│   └── tests/
├── worker-managed/                         # Optional LiveKit media adapter — not required to ship
│   ├── main.py
│   ├── providers/
│   └── tests/
├── core/                                   # Shared across both worker planes
│   ├── transport/                          # File 1 §3.4 BaseTransportGateway + adapters
│   │   ├── livekit_webrtc.py
│   │   ├── native_websocket.py
│   │   ├── twilio_media_stream.py
│   │   └── direct_sip.py
│   ├── fsm/                                # File 2 §2
│   ├── vad/                                # File 2 §1, File 3 §2 VAD
│   ├── providers/                          # File 3 registry + adapters (stt/llm/tts/s2s)
│   ├── language/                           # File 4 router, normalizer, profiles
│   ├── mcp/                                # File 6 §2 MCPHost
│   ├── rag/                                # File 6 §3 retriever + speculative retrieval
│   └── tests/
├── post-call/                              # File 5, generalized from awaazlabs
│   ├── extraction/
│   ├── verification/
│   ├── summarization/
│   ├── webhook_dispatcher/
│   ├── follow_up/
│   ├── longitudinal_memory/
│   ├── redaction/
│   └── tests/
├── telephony-gateway/                      # File 7 §4
│   ├── sip_trunk/
│   ├── transcoding/
│   ├── warm_transfer/
│   └── outbound_campaign/
├── admin/                                  # habiba admin/ pattern, AUDIT_04 §1
├── tenant-portal-api/                      # habiba tenant_portal_api/ pattern
├── agent-studio/                           # File 8 §5 builder UI
├── live-monitor/                           # File 7 §5
├── sdk/
│   ├── python/
│   ├── typescript/
│   └── flutter/
├── examples/
│   ├── web-client/
│   └── host-backend/
├── tests/
│   ├── integration/
│   ├── latency-benchmarks/                 # §3 below
│   └── e2e/
├── infra/
│   ├── docker/
│   ├── helm/
│   └── terraform/
└── .github/workflows/                      # habiba pattern (only legacy repo with in-repo CI, AUDIT_04 §6), extended to the whole monorepo
```

---

## 2. Phase-by-Phase Sprint Plan

Six phases, ordered by dependency, not by file number — File 1's topology is the prerequisite for everything, but the phases pull specific pieces from multiple blueprint files at once because that's how the actual build dependency graph runs.

### Phase 1 — Core Engine (sovereign plane first)
- `core/fsm/` (File 2 §2), `core/transport/native_websocket.py` (File 1 §3.4, File 7 §3.2)
- Bounded queues with standardized overflow policy (File 2 §1.1)
- Barge-in protocol on the **in-process** plane (File 2 §3.1) — not LiveKit-delegated
- **Exit criteria:** a session can connect on native WS, hold a turn-taking conversation, and survive barge-in without audio bleed-through, **with LiveKit unconfigured**. Optional `livekit_webrtc.py` may exist as a stub; it is not an exit gate.

### Phase 2 — Provider Adapters
- `core/providers/` full registry + failover router (File 3 §4, §5)
- Language router + normalizer (File 4 §2, §3)
- Local adapters registered: `faster_whisper`, `piper` (or Coqui), `ollama` — even if quality is behind commercial
- **Exit criteria:** swapping STT/LLM/TTS is a config change; a **forced kill of the primary** vendor (Gladia / Groq / Uplift) still completes a turn via the next route within the circuit-breaker window. A one-name priority list fails startup (File 1 §3.6, File 3 §6 #4).

### Phase 3 — Telephony Bridge
- `telephony-gateway/` (File 7 §2–4), `DirectSIPTransport` first (habiba Telnyx pattern as *one* trunk)
- Second trunk adapter (`generic_pta` or Twilio SIP) before calling PSTN "production"
- `TwilioMediaStreamTransport` as an additional media adapter once one SIP path is proven
- **Exit criteria:** inbound PSTN reaches the same pipeline core as native WS, with μ-law↔PCM16 transcoding (File 7 §2.2), **without requiring LiveKit** for the call to connect. LiveKit SIP remains optional convenience.

### Phase 4 — MCP / RAG Layer
- `core/mcp/`, `core/rag/` (File 6)
- `post-call/` full pipeline (File 5) — built in parallel with MCP/RAG since post-call extraction and live RAG share the same vector store (File 5 §8, File 6 §3.1) and schema-driven-extraction infrastructure benefits from being designed alongside retrieval
- **Exit criteria:** a tenant can register an MCP server and a knowledge base, have both correctly isolated as DATA-framed content (File 6 §1), and see a structured `CallRecord` land in a webhook target after a test call.

### Phase 5 — SDKs & Agent Studio
- `sdk/{python,typescript,flutter}` (File 8 §4)
- `agent-studio/` (File 8 §5)
- **Exit criteria:** a developer with zero backend access can build, configure, and test-call an agent end-to-end through the Studio UI alone.

### Phase 6 — Benchmark & Hardening
- Latency benchmark harness (§3 below) run against the Phase 1–5 build
- Security review pass against every anti-pattern flagged across Files 1–8 (there's a consolidated list in §5 below)
- Load testing the control plane's admission logic (habiba's rate-limiter was flagged as in-process/non-distributed, AUDIT_04 §5 — this must be validated as fixed via the Redis-backed approach from File 1 §3.3 before this phase closes)

---

## 3. Benchmarking & Testing Harness

### 3.1 Latency waterfall tracing

Per-session, per-turn tracing across every stage in File 1 §4's budget table:

```python
class LatencyWaterfall(BaseModel):
    session_id: str
    turn_id: str
    vad_end_of_speech_ms: float
    stt_final_ms: float
    llm_ttft_ms: float
    chunker_ms: float
    tts_ttfb_ms: float
    playback_start_ms: float
    total_e2e_ms: float
```

Metric-emission points already exist as a pattern in three of four legacy repos (v3/multilingual emit `metric` WS events for Gemini/Gladia/Uplift/Total latency, AUDIT_01 §4, AUDIT_03 §4; habiba's SDK exposes `metrics_updated`, AUDIT_04 §4) — this harness formalizes that ad hoc per-repo metric emission into one structured trace format, unified per File 8 §3's event vocabulary.

### 3.2 Evaluation metrics

| Metric | Method | Target (from File 1 §4) |
|---|---|---|
| WER (Word Error Rate) | STT output vs. ground-truth transcript on a fixed audio test set, per language | Provider-dependent baseline, tracked over time not absolute-gated |
| E2E latency (p50/p95/p99) | `LatencyWaterfall` aggregation | p50 <450ms cascaded, <350ms S2S |
| Barge-in accuracy | Synthetic interruption injection at known timestamps; measure false-positive rate (verification window rejects real interruption) and false-negative rate (background noise triggers false barge-in) | <5% false positive, <2% false negative, calibrated against multilingual's 700ms/300ms constants (File 2 §3.1) as starting point |
| Audio MOS (Mean Opinion Score) | Automated MOS estimation (e.g. via a no-reference audio quality model) on TTS output post-transcoding | Provider-dependent baseline |
| Code-switch handling accuracy | Test set of intentionally mixed-script utterances vs. `TextNormalizer` (File 4 §3.1) mis-flag rate | Track against habiba's measured CER data point (0.14 vs 0.43, File 4 §1) as the reference methodology |

### 3.3 Test coverage inheritance

**Explicit note per Rule 8 of the original audit protocol:** the four legacy repos have wildly uneven test coverage (AUDIT_05 §1 matrix: v3 "live-API scripts" only; awaazlabs "essentially ABSENT"; multilingual has real barge-in/language test suites; habiba has 60+ pytest modules + CI). UCVE **cannot** inherit a unified test harness from all four — habiba's `tests/` directory (AUDIT_04 §1, §6) and multilingual's targeted tests (`test_barge_in_verification.py`, `test_orchestrator_arabic.py`, `test_replayable_iterator.py`, AUDIT_03 §6) are the two worth porting test *patterns* from, not literal test files, since they're testing repo-specific implementations that no longer exist in this form post-synthesis.

---

## 4. Deployment & Infrastructure Blueprint

### 4.1 Container strategy

| Service | Base image pattern | Provenance |
|---|---|---|
| Control plane, admin, tenant-portal-api | Python 3.12-slim, per-service Dockerfile under `docker/` | habiba's `docker/{worker,control-plane,admin,tenant-portal-api}.Dockerfile` split, AUDIT_04 §1 — kept as-is, this is good separation |
| worker-managed | Python 3.12, `OMP_NUM_THREADS=1`, `MALLOC_TRIM_THRESHOLD_` tuning | habiba `docker/worker.Dockerfile`, AUDIT_04 §5 memory notes |
| worker-raw | Python 3.11-slim | multilingual's Dockerfile pattern (AUDIT_03 §1), **with the fix** that torch/numpy must be explicitly declared in this image's requirements — multilingual's own Dockerfile does `pip install -r requirements.txt` where torch/numpy are undeclared, meaning the audited image likely cannot load Silero at all (AUDIT_03 §2: "Dockerfile therefore does not install torch. Runtime Silero depends on undeclared deps — NOT VERIFIED that the image can load Silero.") — **do not repeat this in the unified build; it is a plausible outright breakage, not a style nit** |
| Note on v3 | No Dockerfile exists at all in the audited repo (AUDIT_01 §1: deployment was Render via `render.yaml` only) — UCVE containerizes this worker properly rather than depending on a PaaS-specific buildpack |

### 4.2 Kubernetes / Helm

- Control plane: horizontally scalable, stateless (session state moved to Redis per File 1 §3.3, closing habiba's in-process rate-limiter gap, AUDIT_04 §5)
- Workers (both planes): scale on active-session count, not CPU alone, since Silero inference is pooled per-process (File 1 §3.2) and process count directly bounds concurrent session capacity
- GPU note: none of the four legacy repos use GPU inference anywhere (Silero runs CPU-only, AUDIT_01 §2). **Default deploy is CPU-only, self-hosted Postgres + Redis + the worker-raw image** (File 1 §3.6 Tier 0–1). GPU (vLLM) and LiveKit Cloud are optional tracks, not the install path. Helm/Terraform exist for scale; `docker compose` of control-plane + worker-raw + postgres + redis must be a documented, tested single-node product.

### 4.3 CI/CD

Adopt habiba's GitHub Actions structure wholesale — it's the only one of the four with in-repo CI (AUDIT_04 §1: `.github/workflows/{ci,deploy-staging,deploy-prod,release-sdk,refresh-voice-previews}.yml`) — extended to the full monorepo. Staging/prod deploys must **not** assume a single cloud account (LiveKit Cloud project, one STT key, one SIP carrier) as the only green path; CI should run the kill-switch matrix in File 1 §3.6 against mocks.

---

## 5. Consolidated Anti-Pattern Checklist (cross-file index)

Every one of these was a specific, cited bug or gap in a legacy repo. This is the Phase 6 hardening checklist — verify each is actually fixed in the built system, not just documented as "should be fixed" here:

| # | Anti-pattern | Source repo | File where the fix is specified |
|---|---|---|---|
| 1 | Sync blocking calls on event loop at session init (also: sync DB inside async tool handlers) | v3, habiba tools | File 1 §3.2, File 2 §5.1, File 6 §2.2 |
| 2 | Unbounded queues | v3 (MULTI queues are bounded; MULTI still has unbounded `ReplayableAsyncIterator._consumed` per turn) | File 2 §1.1 |
| 3 | Fire-and-forget on a must-await callback | multilingual | File 2 §5.2 |
| 4 | Secrets embedded in URLs | multilingual | File 2 §5.3, File 3 §6 |
| 5 | Unbounded per-session resource construction | v3 Silero+HTTP; multilingual TTS HTTP (Silero is pooled) | File 2 §5.4 |
| 6 | Invalid FSM transition logged but still applied | multilingual | File 2 §2.2 |
| 7 | STT `language` collected but never read (v3); `confidence` never collected in any of the four | v3 (language); all four (confidence) | File 3 §2 (Transcript model), File 5 §4 |
| 8 | Fail-open auth secrets | awaazlabs | File 5 §6 |
| 9 | Idempotency gaps (missing required field still "succeeds") | awaazlabs | File 5 §6 |
| 10 | No retry/backoff on inter-service HTTP forwarding | awaazlabs | File 5 §6 |
| 11 | Capability table / adapter default mismatch | habiba | File 3 §6 |
| 12 | In-process, non-distributed rate limiter | habiba | File 1 §3.3, File 9 §4.2 |
| 13 | No client pong / reconnect handling | v3, multilingual | File 7 §3.2 |
| 14 | Undeclared runtime dependency in Docker image (torch/numpy) | multilingual | File 9 §4.1 |
| 15 | Barge-in discards the triggering utterance | v3 | File 2 §3.1 |
| 16 | Aggressive word-count TTS split cutting mid-code-switch | v3, multilingual | File 4 §3.2 |
| 17 | No zero-retention/PII redaction path | all four | File 5 §9 |
| 18 | Single-vendor STT/LLM/TTS (or LiveKit as the orchestrator) | v3 chain; habiba ur path + AgentSession | File 1 §3.6, File 3 §5.2 / §6 #4, File 2 §3.2 |
| 19 | Single PSTN carrier as the only way to place/receive a call | habiba Telnyx+LiveKit SIP | File 7 §4.1, File 1 §3.6 |
| 20 | Extra SaaS for vectors/auth when Postgres+HMAC already exist | Clerk bypass (MULTI); Qdrant-as-required | File 6 §3.1, File 1 §3.5–§3.6 |

---

## 6. Autonomy & Non-Dogmatic Directive for Cursor

**Read this section before writing a single line of implementation code.**

### 6.1 Living Architecture Principle

Files 1 through 8 of this blueprint, and the five audit reports underneath them, are **strategic documents produced by static analysis** — a snapshot of what four codebases looked like on the audit date, and a synthesis of what to build from that snapshot. They are not immutable dogma, and they were never meant to be treated as a spec that overrides what you find when you actually start implementing.

Specifically:

- If a citation in these files turns out to be wrong once you're looking at the live code during implementation (files move, refactors happen, the audit made an error) — **trust the code, not the document.** Update the document to match reality, don't force reality to match a stale citation.
- If a "best-of-breed" component identified in AUDIT_05 §2 turns out to have a hidden dependency or a subtler bug than the static audit could catch (static analysis has real limits — it cannot verify actual runtime behavior, per every audit's own repeated "NOT MEASURABLE VIA STATIC AUDIT" caveats), you have full license to swap in a different implementation and document why.
- If a design decision in Files 1–8 conflicts with something you learn only by building (a Pydantic pattern that doesn't actually compose well with the chosen web framework, a "generalize this" instruction that turns out to need two separate abstractions instead of one) — **adapt the schema, refactor the data model, and update the relevant blueprint file.** These files should evolve alongside the codebase, not ossify as day-one documentation nobody trusts by month three.

### 6.2 What stays fixed

Autonomy is not unlimited. The following are **not** subject to opportunistic reinterpretation without an explicit, documented reason:

- The **child-safety, security, and compliance postures** established across Files 5, 6, and 7 (DATA-framing of untrusted content, fail-closed secrets, PII redaction ordering, calling-window enforcement) are load-bearing safety properties, not style preferences. Changing them requires the same rigor as changing them would in a security review — a written rationale, not a silent refactor.
- The **product-sovereignty rules** in File 1 §3.6 (Tier 0 IP stays in-process; ≥2 routes per critical vendor category; native WS + Direct SIP must work with LiveKit unconfigured) are load-bearing. Convenience adapters (LiveKit Cloud, Gladia, Uplift, Telnyx, Groq) may be added or swapped; they may not become the only path.
- The **evidence-based citation discipline** that produced this blueprint should carry forward into its implementation: when Cursor deviates from a documented decision, it should say so in code comments or commit messages with the same "here's what I found, here's why" rigor the audits themselves used — not silently diverge.
- **Zero-modification of the original four legacy repos** (Rule 1 of the audit protocol) no longer applies once this blueprint phase begins — implementation necessarily means writing new code in the new monorepo (§1) — but the legacy repos remain the historical reference; don't delete or overwrite them, since File-level citations throughout this blueprint depend on them still being inspectable for provenance-checking during the build.

### 6.3 Practical instruction

When you, Cursor, encounter a gap between this blueprint and implementation reality: **inspect, decide, implement, then update the relevant blueprint file(s) with a short note explaining the change and why.** Treat these 9 files as a living design doc under version control alongside the code, not a one-time handoff artifact to be read once and forgotten.
