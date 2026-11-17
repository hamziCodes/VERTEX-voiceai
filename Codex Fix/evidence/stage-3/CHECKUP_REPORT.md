# Stage 3 — Engine checkup as a real customer

Branch `wavia-fixv1`, from `369a1df` (Phase 15 close). All fixes are atomic commits with tests.

## Result

| Check | Result |
|---|---|
| Real-chain customer journey, mock providers (release images, PostgreSQL, Redis, S3Mock, offline WorkOS double) | **8/8 pass**: sign-up → workspace → onboarding → publish → browser voice test (real VAD, measured latency) → conversations + post-call summary → API key + SDK quickstart → knowledge ingest/activate/connect → signed webhook endpoint |
| Python suite | 1204 passed, 23 skipped |
| Live PostgreSQL suite | 65 passed, 1 skipped |
| Studio | 232 unit tests, typecheck, lint, production build; offline browser suite 43 passed |
| H15 **L1** provider reachability | Gladia, Deepgram, Groq, Gemini, OpenAI, Cartesia, ElevenLabs: HTTP 200. Uplift: no ping endpoint. **Telnyx: HTTP 401 (key rejected)** |
| H15 **L2** live pipeline | Sign-up, onboarding and publish pass live; **voice test blocked**: the `.env` names the Gemini key `GOOGLE_API_KEY`, but the engine reads only `PLATFORM_GEMINI_API_KEY`, and Gemini is the default LLM fallback route |

## Failures found and fixed

| Problem as a customer met it | Fix |
|---|---|
| No way to sign up or create a first workspace | `465fc2d` self-serve sign-up + workspace creation |
| Sign-in redirect loop (localhost vs 127.0.0.1) | `42ea939` |
| New agent page 404 (no versions) | `2e0bc48` |
| Templates could not publish (uncatalogued provider) | `52f40e8` |
| API key could not mint (demo tenant forced) | `cffd75e` |
| No agent IDs or snippet beside API keys | `e8a9f16` |
| Post-call summary never produced; Studio read the wrong fields | `f8801df`, `e62d9dc` |
| Webhooks: no self-serve endpoints; nothing auto-delivered | `46f8131`, `5efe4ff` (deliver automatically unless the review policy flags the call) |
| Knowledge stuck at "queued" (no parse job, per-container storage) | `1438ed7` |
| Embedding failed for the non-root image user (errno 13) | `84c029d`, `ab68268` (pinned e5-small, SHA-256 verified, baked into images) |
| Every signed-in admin refused when adding a webhook or approving a review, shown as "did not resolve" | `276a247` one permission rule for routes and repositories |
| `.env.example` claimed AWS KMS for production; nothing selected it | `0515df9` explicit `UCVE_KMS_BACKEND=local\|aws` |
| Env docs: unused vars, misnamed keys, missing vars | `51e97ff` |
| Next.js advisory GHSA-mfr8-8qww-v76h; the dev server also stopped itself mid-run | `8bde642` Next 16.4.6, `npm audit` 0 |
| Live session refused silently; Studio said "worker unavailable"; readiness said "Ready to publish" | `55c6191`, `87139a6`, `631ae2c` |
| L2 could never pass (demo tenant never uses platform keys); Windows path bugs | `51ad738`, `31737ce` |

## Open items

1. **`.env`**: add `PLATFORM_GEMINI_API_KEY` (same value as `GOOGLE_API_KEY`), then rerun L2. Agents must not edit key files without the owner's permission.
2. **Telnyx key** is rejected (401); it needs replacing before L4.
3. **Real WorkOS staging sign-in** needs the redirect URI registered in WorkOS (`NEXT_PUBLIC_WORKOS_REDIRECT_URI`).
4. **Deploy config (not touched):** `infra/docker/docker-compose.staging.yml` points OTLP at `jaeger:4317`; the exporter is OTLP/HTTP on 4318.
5. **Images:** the release images were not rebuilt after `55c6191`/`631ae2c`. Rebuild `control-plane` and `worker-raw` before the next stack run.
6. **Readiness check:** it runs only in "Check readiness". The publish API does not yet refuse a chain with missing keys.
7. **L4–L8** (telephony, AWS, publishing, deploys) still need separate approval.
