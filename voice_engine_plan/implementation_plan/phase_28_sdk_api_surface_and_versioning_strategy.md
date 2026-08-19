# Phase 28: SDK/API Surface and Versioning Strategy

## 1. Executive Summary & Core Logic

Deliver the external developer surface: OpenAPI 3.1 control-plane spec, unified realtime event protocol (File 8 §3), and client SDK scaffolds (Python, TypeScript primary; Flutter roadmap) with explicit **versioning and compatibility rules**. Generalizes habiba browser SDK zero-secret pattern (`legacy_codebases/habiba-sdk-agent/sdk/src/index.ts` — publishableKey + host backend mint, AUDIT_04 §2 transport) to sovereign native WS default (File 1 §3.6). TypeScript SDK location deferred from Phase 00 — lands here at `sdk/typescript/`.

Depends on Phase 13 auth/HMAC mint, Phase 17 WS transport, Phase 25 error codes, Phase 26 agent config schema, Phase 08 OpenAPI base routes, Phase 24 client playback events.

**Flutter:** **roadmap only in v1** — not a blocker; web/JS SDK primary. **LiveKit:** **separate optional package** `@ucve/voice-livekit`, not core SDK dep. **OpenAPI hosting:** **self-hosted** on control-plane `/docs` (Redoc/Swagger UI), not third-party SaaS docs platform.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| OpenAPI 3.1 + `openapi-typescript` codegen | Single spec → TS types |
| Semantic versioning on API (`/v1/`) | habiba `/v1/` pattern preserved |
| SDK major version tracks breaking WS event changes | Client/server coupling explicit |
| Zero secrets in client SDK | habiba AUDIT_04 §4 — keys stay on host backend |
| Native WS default; LiveKit optional package | File 8 §4.1; Phase 18 optional adapter pattern |
| Self-hosted API docs | Compliance posture — self-managed infra (Phase 08 Postgres decision) |

**Reference docs:** blueprint File 08 §2–4; habiba `sdk/src/index.ts`; File 07 §3.2 pong/reconnect client duties.

## 3. What / How / Why

- **What:**
  - **`openapi.yaml`** — full control plane: mint, agents CRUD (Phase 26), usage (Phase 14), extraction schemas (Phase 21), knowledge bases (Phase 23), telephony (Phase 18/19), auth (Phase 13)
  - **Self-hosted docs:** FastAPI `/docs` (Swagger) + `/redoc` on control-plane — **no ReadMe.io/Stoplight SaaS hosting**
  - **Realtime protocol doc** — `UCVERealtimeEvent` union (File 8 §3) + binary audio framing; includes **`control.playback_started`** (Phase 24)
  - **SDK scaffolds (v1 primary):**
    - `sdk/python/ucve/` — `UCVEVoiceClient` async (File 8 §4.1) — **full v1**
    - `sdk/typescript/` — `UCVEVoiceClient` + `useUCVEVoice` hook (File 8 §4.2) — **full v1**
    - `sdk/flutter/` — **`ROADMAP.md` + minimal stub** — connect/disconnect types only; **not v1 parity blocker**
  - **`@ucve/voice-livekit` (optional package):** separate npm package wrapping Phase 18/19 LiveKit adapter — **not imported by default SDK build**; tree-shakeable opt-in
  - **Client responsibilities:** send `control.pong` on server ping; emit `control.playback_started` on first audio output; basic reconnect = new mint + connect (Phase 17 scope)
  - **`SDKVersion` manifest:** `{api_version, event_schema_version, min_server_version}`
  - **Versioning policy (`docs/sdk/VERSIONING.md`):** patch/minor/major rules; 2-minor deprecation window REST; 1-release WS event deprecation
- **How:** OpenAPI generated from FastAPI routes where implemented; hand-maintained for spec-ahead routes. Default SDK build excludes LiveKit. Flutter stub documents planned API surface without shipping full client. CI: schema diff check on PR.
- **Why this approach:** Three legacy repos had three event vocabularies (File 8 §3 table). **Flutter parity deferred** — web/JS is primary integrator surface for v1. **LiveKit separate package** maintains Phase 18 "optional adapter, not load-bearing" consistency. **Self-hosted docs** matches self-managed Postgres/compliance posture.

## Deliverables

- `openapi.yaml` — control plane spec
- `control-plane/openapi_serve.py` — self-hosted `/docs` + `/redoc`
- `docs/sdk/VERSIONING.md`
- `docs/sdk/REALTIME_PROTOCOL.md` — events + audio framing + playback_started
- `docs/sdk/HOST_BACKEND_MINT_GUIDE.md` — zero-secret integration pattern
- `docs/sdk/FLUTTER_ROADMAP.md` — v1 non-blocker; planned parity milestones
- `sdk/python/pyproject.toml` + `ucve/client.py`
- `sdk/typescript/package.json` + `src/client.ts` + `src/hooks/useUCVEVoice.ts`
- `sdk/typescript-livekit/package.json` — **`@ucve/voice-livekit` optional package**
- `sdk/flutter/ROADMAP.md` + `lib/ucve_voice_client_stub.dart` — stub only
- `sdk/shared/event_schema.json` — JSON Schema for WS events
- `.github/workflows/sdk-schema-check.yml` — breaking change detector stub
- `examples/host-backend/` — minimal mint proxy (Python FastAPI)

## 4. Compute & Resource Profile (if applicable)

SDK client footprint: TS ~15 KB gzipped (no LiveKit dep in default build). Mint proxy example: negligible. Schema CI: ~10 s per PR. Self-hosted docs: served from control-plane — no external dependency.

## 5. Compliance Notes (if applicable)

SDK must never accept provider API keys in constructor — lint rule enforced. Mint guide documents PHI boundaries — host backend responsible for caller consent before session start. OpenAPI documents data classes on sensitive fields (Phase 10). Self-hosted docs avoid third-party doc platform subprocessors.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Flutter priority:** **roadmap only for v1** — not a blocker; web/JS SDK primary; stub + `FLUTTER_ROADMAP.md`.
2. **LiveKit SDK:** **separate optional package `@ucve/voice-livekit`** — not bundled in core SDK; consistent with Phase 18.
3. **Public OpenAPI hosting:** **self-hosted** on control-plane `/docs` + `/redoc` — no third-party SaaS docs platform.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_28_sdk_api_surface.py`
- **Asserts:** OpenAPI validates; self-hosted docs route registered; SDKVersion manifest present; python + typescript SDK instantiate; flutter stub + roadmap doc exist; `@ucve/voice-livekit` package separate from core TS build; event schema covers File 8 §3 table + playback_started; SDK constructor rejects raw API keys; mint guide documents HMAC flow; breaking-change CI detects removed field in fixture diff.
- **Pass threshold:** 100% structural/SDK smoke tests.
- **Latency target:** N/A (contract tests); example client connect < 2 s to mock server.
