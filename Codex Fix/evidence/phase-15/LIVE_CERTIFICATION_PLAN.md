# Phase 15 — live certification plan (H15, prepared, NOT executed)

Every step below needs Hamzi's separate, explicit approval. Nothing here has
been run. Steps L1–L2 are scripted with a hard refusal unless
`WAVIA_LIVE_APPROVED=<step>` is exported; the rest are operator runbooks.
Spend ceilings are proposals for Hamzi to confirm or change; set each
provider's own budget alert or hard limit to the same value before running.

| Step | What it proves | Command / action | Cost ceiling (proposed) | Reversible |
|---|---|---|---|---|
| **L1** Provider reachability | Each configured key is valid and the account is active | `WAVIA_LIVE_APPROVED=L1 bash scripts/release/live_certification.sh L1` (read-only list/metadata GETs to Gladia, Deepgram, Groq, Gemini, OpenAI, Cartesia, ElevenLabs, Telnyx; Uplift: key-present check only) | $0 expected (no generation) | Yes — nothing created |
| **L2** Live voice pipeline | The real customer journey on release images with live STT/LLM/TTS: sign-up → publish → browser voice test → post-call summary by a real model → API key + SDK quickstart (Stage 3 rework: demo-tenant sessions never use platform keys, so the old session loop could not pass) | `WAVIA_LIVE_APPROVED=L2 bash scripts/release/live_certification.sh L2` (root `.env` passed to Docker with `--env-file`; every enabled chain route needs its `PLATFORM_<PROVIDER>_API_KEY`) | ≤ US$5 across providers (two short voice sessions + one summary) | Yes — disposable stack, removed after |
| **L3** Live latency corpus | End-of-speech → first audible sample on real speech (FLEURS, H02) with live providers; p50/p95/p99 | Requires (a) accepting the FLEURS licence: `python tests/latency/fixtures/fetch_fleurs.py --accept-license` (Hugging Face download, pinned revision) and (b) a live-mode corpus runner, **which does not exist yet**: `tests.latency.baseline` is offline by design and denies network. Building it is Stage 3 work | ≤ US$10 | Yes |
| **L4** Telephony | Telnyx inbound + outbound call through the gateway, recording consent, post-call record | Buy one Telnyx DID in the target country; point its Call Control app at a reachable gateway URL; place one inbound and one outbound call (≤ 2 min each) with `RUN_LIVE_TELEPHONY=1` | One DID for one month + ≤ 10 call-minutes; ceiling US$15 | DID can be released; calls are not reversible |
| **L5** AWS me-central-1 services | Real S3 (object store + prefix sweep), KMS (envelope keys), RDS PostgreSQL + pgvector (migrations 001–036, RLS), ElastiCache Redis | Provision the smallest instance classes in a sandbox account, run `container_stack.sh`-equivalent services against them, then `bash scripts/ops/run_privacy_proof.sh` and `scripts/ops/drill_backup_restore.sh` pointed at them; tear down the same day | ≤ US$10 for one day | Yes if torn down; deletion of KMS keys has a waiting period |
| **L6** Package publishing | SDKs installable from public registries | `uv publish` of `ucve_voice_sdk-1.0.4` wheel/sdist; `npm publish` of `@ucve/voice-sdk-1.0.4.tgz` (artifacts and SHA-256 in `hamza_local/phase15/sdk/SHA256SUMS`) | $0 | **No** — a published version can be yanked/deprecated but never reused |
| **L7** Staging deploy | Images run on the chosen hosting target behind TLS | Push images to a registry; deploy ECS services with `/health/ready` probes; smoke: SDK quickstart against the staging URL | Hosting cost while running | Yes |
| **L8** Production deploy | — | Only after L2–L7 pass and Hamzi signs the release candidate | — | Rollback plan in `docs/release/ROLLBACK.md` |

## Decisions Hamzi must make before L6

1. **Package names.** The SDKs are still named `ucve-voice-sdk` (PyPI) and
   `@ucve/voice-sdk` (npm), with the `ucve` import namespace. Publishing
   fixes those names permanently. Rename to Wavia before the first publish?
2. **SDK version.** SDKs are 1.0.4 while the server is 0.1.0 and the realtime
   protocol is 1.0.0. A `1.x` SDK signals stability; consider publishing the
   first public release as `0.x` to match the server.
3. **Licence.** The TypeScript package declares Apache-2.0 but the repository
   has no LICENSE file, and the Python package declares none. A licence file
   and matching metadata are needed before publishing.
4. **psycopg (LGPL-3.0)** ships unmodified in every server image as a
   dynamically imported library. Normally acceptable; confirm.

## What remains unverified until these run

Live STT/LLM/TTS behaviour and cost, real end-of-speech → first-audio latency,
carrier media and consent, real AWS S3/KMS/RDS/ElastiCache behaviour, registry
publishing, and any hosted environment.
