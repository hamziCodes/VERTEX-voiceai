# Wavia — Handover

Last updated 2026-11-17. This is a summary of what is done and what remains. Detail lives in the documents it links to.

## Branches

| Branch | State | What it holds |
|---|---|---|
| `wavia-fixv1` | Pushed (`3bc3b32` before this doc) | Engine, control plane, Studio dashboard, release tooling, Stage 3 fixes |
| `website` | Pushed (`b4138aa`) | Marketing site in `website/` (C2 · Ripple Paper), 127 commits ahead of `main` |
| `main` | Not updated | Nothing has been merged; merging is the owner's call |

## Where to read more

| Topic | Document |
|---|---|
| Phase-by-phase status and commit lists | [Codex Fix/EXECUTION_TRACKER.md](Codex%20Fix/EXECUTION_TRACKER.md) |
| Decisions waiting on the owner (H1–H15) | [Codex Fix/HUMAN_INPUT.md](Codex%20Fix/HUMAN_INPUT.md) |
| Stage 3 customer checkup (latest) | [Codex Fix/evidence/stage-3/CHECKUP_REPORT.md](Codex%20Fix/evidence/stage-3/CHECKUP_REPORT.md) |
| Release notes, compatibility, support, rollback | [docs/release/](docs/release/) |
| Live certification steps L1–L8 | [Codex Fix/evidence/phase-15/LIVE_CERTIFICATION_PLAN.md](Codex%20Fix/evidence/phase-15/LIVE_CERTIFICATION_PLAN.md) |
| Configuration (every variable the engine reads) | [.env.example](.env.example), [docs/sdk_documentation/07-configuration.md](docs/sdk_documentation/07-configuration.md) |
| Design system (website and dashboard) | `website/docs/design/ripple-c2/RIPPLE-C2-MASTER.md`, [docs/DESIGN.md](docs/DESIGN.md), [docs/design/design-tokens.json](docs/design/design-tokens.json) |
| Website decisions | `website/DECISIONS-STAGE4.md` (on `website`) |

## Done

### Engine phases 0–15 (see the tracker)
- **Phases 0–12 complete.** Real-time voice pipeline (VAD, streaming STT, LLM, TTS, barge-in, failover), tenancy with PostgreSQL row-level security, auth and RBAC, durable knowledge/RAG, privacy and the call lifecycle, post-call intelligence, review, signed webhooks, and Telnyx telephony.
- **Phase 13 (Studio):** built and pushed. The final screenshot approval (exit 8) is still the owner's.
- **Phase 14 (cleanup):** complete offline. A proposed delete list awaits the owner.
- **Phase 15 (packaging and release qualification):** complete offline.
  - Release images are rendered from one template, with pinned, hash-checked dependencies.
  - The qualification stack is `scripts/release/container_stack.sh`.
  - Release docs are written.

### Stage 3 — checkup as a real customer (this session)
The full journey runs on the release images in mock-provider mode and passes **8/8**:
- sign-up → workspace → onboarding → publish an agent
- browser voice test with real VAD and measured latency
- conversations plus post-call summary
- API key plus SDK quickstart
- knowledge upload → parse → embed → activate → connect
- signed webhook endpoint

Command: `studio/playwright.journey.config.ts` (start the stack with `WAVIA_STACK_IDP=1` first).

Fixed along the way (commits in the checkup report):
- **Self-serve sign-up:** no way to sign up or create a first workspace; sign-in redirect loop.
- **Agents:**
  - New agents 404'd.
  - Templates could not publish.
  - "Check readiness" passed agents whose providers had no key.
- **API keys and SDK:** API keys could not mint sessions, and Studio had no integration details.
- **Post-call:** summaries were never produced, and Studio read the wrong fields.
- **Webhooks:**
  - Self-serve endpoints added; delivery is automatic unless the review policy flags the call.
  - Every signed-in admin was refused when managing webhooks or reviews, because routes and repositories used different permission rules.
- **Knowledge:** stuck at "queued". Fixed with a parse job, shared S3 storage, and the pinned e5-small embedding model baked into images (SHA-256 verified, readable by the non-root user).
- **Live sessions:**
  - Sessions refused silently.
  - Studio said "worker unavailable" and timed out live sessions after 3 s.
  - The worker logged nothing.
- **Security and config:**
  - Next.js security advisory: now 16.4.6, and `npm audit` reports 0.
  - KMS backend is now an explicit `UCVE_KMS_BACKEND=local|aws`. AWS KMS was documented but never wired.
  - `.env.example` and the SDK docs now list exactly what the engine reads, with platform keys as `PLATFORM_<PROVIDER>_API_KEY`.
- **Release tooling:** the live-check script (L2) could never pass; it was reworked to run the real journey with live providers. Windows path bugs in the release scripts were fixed.

Test state:

| Suite | Result |
|---|---|
| Python | 1204 passed, 23 skipped |
| Live PostgreSQL | 65 passed, 1 skipped |
| Studio | 232 unit tests, typecheck, lint, build, and 43 offline browser tests pass |

### H15 live checks
- **L1 (read-only provider ping):** passed for Gladia, Deepgram, Groq, Gemini, OpenAI, Cartesia and ElevenLabs. Uplift has no ping endpoint. **Telnyx rejected the key (401).**
- **L2 (live pipeline):** sign-up, onboarding and publish pass live. The voice step was blocked by the Gemini key name. `PLATFORM_GEMINI_API_KEY` has since been added to the local `.env`, but L2 has not been rerun.

### Stage 4 — website (`website` branch)
- C2 · Ripple Paper site: Aubergine/Lime/Lilac/Bone, Instrument Serif and Space Mono.
- Immersive landing page with one persistent call object.
- Informative pages: product, how it works, studio, developers and docs, pricing, custom, about, contact, privacy, terms.
- `/demo` dashboard on labelled sample data, and an auth hand-off to Studio.
- Playwright route check and screenshots.

## Remaining

### Needs the owner
1. **Telnyx key**: it returns 401. Replace it in `.env` before any telephony step (L4).
2. **WorkOS staging redirect URI**: register it in WorkOS and set `NEXT_PUBLIC_WORKOS_REDIRECT_URI`. This is needed for real sign-in (the journey currently uses the offline WorkOS double).
3. **H15 approvals for L4–L8**: telephony, AWS, publishing and deploys. L1/L2 are already approved.
4. **Phase 13 screenshot approval (exit 8)** and the **Phase 14 delete list**.
5. **Merging** `wavia-fixv1` and `website` into `main`.
6. **Local cleanup**: delete `D:\d` (stray files written by an old path bug, now fixed) and the `Downloads\_env` copy of the keys.

### Engineering work left
1. **Rebuild images, then run L2**:
   - Rebuild `control-plane` and `worker-raw`; they predate commits `55c6191` and `631ae2c`.
   - Then run `WAVIA_LIVE_APPROVED=L2 bash scripts/release/live_certification.sh L2`, capped at ≤ US$5.
   - Stop any Studio dev server on :3100 first.
2. **Studio C2 theming**: restyle the dashboard to the Ripple tokens. Studio still uses the older theme.
3. **SCR-01…SCR-13**: verify each screen against the spec (loading, empty and error states; roles).
4. **Publish guard**: the publish API should refuse a chain with missing keys in live mode. Today only "Check readiness" catches it.
5. **Staging compose OTLP endpoint**: `infra/docker/docker-compose.staging.yml` uses `jaeger:4317`, but the exporter is OTLP/HTTP on 4318. This is deploy config, so it was left untouched under the standing rules.
6. **Stage 4 summary report**: the final summary when the website ships.

## Standing rules (unchanged)
- Engine work happens on `wavia-fixv1` and the website on `website`. Never work on `main`, never force-push.
- Keep `RUN_LIVE_PROVIDERS=0` and `RUN_LIVE_TELEPHONY=0` unless a specific live step is approved.
- No deploy, publishing, number purchase, real calls or spend without approval.
- Never commit `.env` or key files.
- Never edit `.github/workflows` or deploy config.
- The FastAPI control plane is the authorization authority.
- Test doubles must be labelled and must never fake production success.
