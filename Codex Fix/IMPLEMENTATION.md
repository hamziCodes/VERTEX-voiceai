# Wavia Production Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:executing-plans` for native execution, or `superpowers:subagent-driven-development` only if Hamzi explicitly chooses delegated execution. Track work with checkboxes and update this folder after every phase.

**Goal:** Convert the audited Wavia/UCVE repository into a low-latency, tenant-safe, durable, testable production voice-agent platform for packaged SDK, managed enterprise, and self-serve delivery.

**Architecture:** Preserve the sovereign raw WebSocket engine, but compile each published agent into one immutable runtime session plan. Keep microphone-to-playback work streaming and bounded; run management and post-call work through durable stores and jobs. Select external providers and carriers through explicit capability, credential, compliance, and health policy.

**Tech stack:** Python 3.12, FastAPI, asyncio, WebSockets, PostgreSQL/pgvector, Redis, TypeScript/React, pytest, TypeScript tests, Docker Compose, provider HTTP/WebSocket APIs, SIP/RTP adapters.

**Spec:** [`../AUDIT.md`](../AUDIT.md), [`EDUCATION.md`](EDUCATION.md), and [`phases/`](phases/).

## Global constraints

- Latency is the first product gate. Do not start broad platform expansion before Phases 00–04 establish and improve a truthful baseline.
- No live or paid provider/carrier request without Hamzi's explicit approval and a declared spend/destination limit.
- Test doubles are explicit. Production never emits mock transcripts, replies, tones, webhook success, recordings, or extraction results.
- The worker loads a published, tenant-owned, immutable session plan. Query overrides are local-demo-only.
- All queues, buffers, deadlines, retries, tasks, streams, and resource lifetimes are bounded and observable.
- Interruption cancels generation, stops server egress, clears client audio, retains the user's words, and stores only played speech.
- No secrets in code, logs, reports, fixtures, URLs, commits, or chat.
- Management tenant identity derives from authenticated credentials, never an untrusted header.
- Preserve the dirty working tree. Follow the rollback-commit rule in `AGENTS.md` before risky multi-file work.
- Never alter `.github/workflows`, deploy, publish, force-push, or delete without explicit approval.
- Every phase uses focused tests and ends at its verification gate.

## Provisional success targets

Phase 00 records the baseline. Hamzi approves any contractual SLO.

| Metric | Offline gate | Later approved live gate |
|---|---:|---:|
| Acoustic end-of-speech → first audible sample, p50 | ≤ 800 ms | ≤ 1,000 ms |
| Acoustic end-of-speech → first audible sample, p95 | ≤ 1,500 ms | ≤ 1,800 ms |
| Normal clean-speech endpoint contribution | 300–500 ms | tuned per language/noise |
| Confirmed barge-in → silence, p95 | ≤ 200 ms | ≤ 300 ms perceived |
| Stale audio after interruption | ≤ 100 ms | ≤ 300 ms |
| Silent audio/queue loss | 0 | 0 |
| Cross-tenant unauthorized success | 0 | 0 |
| Production mock fallback | 0 | 0 |

## Phase map

| Phase | Name | Outcome | Depends on | Human gate |
|---:|---|---|---|---|
| 00 | Baseline and safety harness | Reproducible offline baseline | — | Reference hardware/browser and fixtures |
| 01 | Truthful latency telemetry | Turn-correlated measurements | 00 | SLO definition |
| 02 | Listening and streaming STT | Warm STT, faster endpoint, bounded ingress | 01 | Endpoint tradeoff after evidence |
| 03 | LLM-to-TTS first audio | Early chunks, real TTS streaming, correct DSP | 01–02 | Later live provider smoke |
| 04 | Interruption and lifecycle | No ghost audio/tasks; accurate played context | 02–03 | Listening acceptance if requested |
| 05 | Protocol and SDK parity | One versioned realtime contract | 04 | Flutter/LiveKit release status |
| 06 | Agent session compiler | Published config drives runtime | 05 | Override policy |
| 07 | Providers and credentials | Real chains, health, failover, typed errors | 06 | BYOK/platform vendors |
| 08 | Authentication and tenancy | Authenticated management and bound mint | 06 | Identity/admin choice |
| 09 | Persistence, migrations, quotas | Correct pgvector/RLS/admission/usage | 07–08 | Disposable DB/Redis |
| 10 | RAG and tools | Durable knowledge and real MCP execution | 07,09 | Tool/data scope and hypercodes |
| 11 | Post-call intelligence | Honest records/extraction/review/webhooks | 09 | Retention/residency/review |
| 12 | Telephony | Offline carrier media lifecycle, staged live plan | 04,07,09 | Carrier/direction/live approval |
| 13 | Self-serve Studio | Nontechnical onboarding to working publish | 05,06,08–12 | Product/UI scope |
| 14 | Operations and compliance | Real jobs/telemetry/readiness/erasure | 09–12 | Hosting/compliance claims |
| 15 | Packaging and qualification | Installable artifacts and release evidence | all release phases | Publish/deploy/live certification |

## Ordering

Phases 00–04 are sequential. After Phase 06, Phases 07 and 08 are independent, but Phase 09 needs both stable. Phases 10 and 11 may proceed independently after Phase 09. Phase 12 may begin offline adapter work after Phase 04 but needs 07/09 for production. Studio and release qualification consume stabilized contracts.

## Per-phase operating procedure

1. Read the phase file, linked findings, and named source files.
2. Resolve `Human gate before implementation`; if it says none, proceed.
3. Record baseline evidence before changes.
4. Create the required rollback commit before risky multi-file work.
5. Implement each task with focused failing test, minimum change, passing test, and reviewable commit.
6. Run automated verification. For expensive commands, give Hamzi one exact command and expected evidence.
7. Run the verification scan in `VERIFICATION.md` and update traceability/evidence.
8. Stop at human gates. Silence is not approval.
9. Mark `COMPLETE` only after all exit criteria pass.

## Rollback and failure policy

- A regression against Phase 00 blocks the phase unless Hamzi accepts the measured tradeoff.
- Revert latency changes that damage word retention, audio quality, language behavior, interruption, or cost accounting.
- Provider/carrier failures return typed errors and degradation events, never fake content.
- Migrations require disposable fresh-install and upgrade tests before any shared database.
- Live certification defects are reproduced and fixed offline/staging, never patched directly in production.

## Completion definition

Production-ready means all release-required gates pass; no critical/high audit finding remains without accepted risk; client packages install and converse; published config controls runtime; auth/RLS isolation is proven; providers fail honestly and fail over where promised; offline telephone media works end to end; durable records/jobs survive restart; observability measures real events; and Hamzi separately approves any live call, spending, publish, or deployment.
