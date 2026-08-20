# Production Foundation Hardening (H0–H6)

Converts Phases 08–17 from in-process contract stubs into a deployable multi-tenant voice foundation. **Phases 18–35 must not execute until `FOUNDATION_READY`.**

Locked defaults: package dirs `control_plane/` + `worker_raw/` (underscores); Gladia/Groq/Uplift behind Phase 05 ABCs; LocalDev KMS only when `UCVE_ENV ∈ {dev,development,test}`; AudioWorklet demo now, full SDKs at Phase 28; dual-column transcript persist now, CRM at 20–21.

## Gate status

| Gate | Status | Sign-off |
|---|---|---|
| `FOUNDATION_HARDENING` | `IN_PROGRESS` | — |
| `FOUNDATION_READY` | blocked until H0–H6 exit | — |

## Execution checklist

| Step | Focus | Exit criteria (summary) | Status |
|---|---|---|---|
| **H0** | Spec, env, packaging spine | Compose postgres+redis healthy; CP/worker images build; `/health` stubs; prod secret refuse | `COMPLETED` |
| **H1** | Crypto + auth | PyJWT HS256; Redis nonce/rate; mint IDOR/quota/origin; no default secrets in prod | `COMPLETED` |
| **H2** | FastAPI CP + worker WS | Routes on 8080; `/ws/audio` on 8081; real transport send | `COMPLETED` |
| **H3** | Postgres + Redis I/O | Migrations 001–009; psycopg repos; vault/audit/usage/Redis survive restart | `COMPLETED` |
| **H4** | Compliance fail-closed | HIPAA BAA override fix; real erasure/purge; dual columns | `COMPLETED` |
| **H5** | Talking pipeline | Silero ONNX; Gladia/Groq/Uplift; TaskGroup orch; AudioWorklet demo | `COMPLETED` |
| **H6** | Hardening suite + gate | `tests/hardening/*` green; integrity OK; tracker `FOUNDATION_READY` | `COMPLETED`* |

\*H6 automated suite green; `FOUNDATION_READY` sign-off still requires local compose health + demo call (Docker not available in this agent environment).


Do not parallelize H1 with H2. H5 may scaffold adapters after H2 connect path exists but must not claim done until H3 + H4 are in.

## Acceptance matrix (`FOUNDATION_READY`)

- [ ] Compose: postgres, redis, control-plane, worker-raw healthy
- [ ] Mint HMAC → JWT → WS audio round-trip with mock providers
- [ ] All H1–H5 automated tests green (`tests/hardening/`)
- [ ] No default crypto material accepted in `UCVE_ENV=production`
- [ ] Vault/audit/usage survive process restart
- [ ] HIPAA/GDPR gates fail closed (including override attack)
- [ ] Demo AudioWorklet client completes a local call
- [ ] Phase 18 not started

## Out of scope

Full Phase 28 SDKs; telephony/SIP (18–19); CRM extraction (20–21); MCP/RAG (22–23); SIEM export; SSML; cross-worker FSM resume; script-aware NER beyond Latin regex.

## Env contract (see `infra/docker/.env.example`)

Required in production (`UCVE_ENV=production`): `UCVE_JWT_SECRET`, `UCVE_MINT_HMAC_SECRET`, `UCVE_METRICS_BEARER` — must be set and must not equal known defaults. Dev may use `UCVE_MASTER_KEY`; prod requires `AWS_KMS_KEY_ID` (or fail-closed).

## Test entrypoints

```bash
python -m pytest tests/hardening/ -v
python voice_engine_plan/scripts/verify_plan_integrity.py
docker compose -f infra/docker/docker-compose.yml up --build
```

Live providers (manual/nightly only): `RUN_LIVE_PROVIDERS=1` with platform API keys present. CI always uses mocks.
