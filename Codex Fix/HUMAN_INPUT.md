# Human Input and Approval Register

The executor records dated answers here. No secret values belong in this file.

| ID | Needed by | Decision or information required | Why it matters | Status |
|---|---:|---|---|---|
| H01 | 00 | Reference machine and separate browser/Telnyx benchmark profiles | Makes baselines comparable | RESOLVED 2026-10-15 — local Windows/Chrome profile recorded; web and calling paths measured separately |
| H02 | 00 | Approved non-sensitive multilingual fixtures | Endpoint/accuracy tuning needs representative audio | RESOLVED 2026-10-15 — Hamzi delegated corpus choice; pinned FLEURS subset selected and legacy mixed-language clip retained for timing |
| H03 | 01 | Acoustic end-of-speech to first audible sample is primary; live thresholds remain provisional | Metric definition fixed; release thresholds await evidence | RESOLVED 2026-10-16 |
| H04 | 02 | Choose aggressive (~400 ms), balanced (~550–650 ms), or adaptive endpoint after evidence | Speed versus cutoff tradeoff | DEFER UNTIL EVIDENCE |
| H05 | 05 | Is Flutter in v1? Is LiveKit offered or roadmap-only? | Decides whether stubs block release | RESOLVED 2026-10-20 — v1 ships the raw-WebSocket Python and TypeScript SDKs; Flutter and LiveKit are explicitly roadmap-only |
| H06 | 06 | May token holders override prompt/providers, or is published config authoritative? | Security and reproducibility | RESOLVED 2026-10-20 — published configuration is authoritative in production; sessions may choose only options explicitly allowed by that version; unrestricted overrides require an explicit local-development-only unsafe flag |
| H07 | 07 | Platform keys, BYOK, or both; required vendors per language | Credential/routing scope | RESOLVED 2026-10-22 — support platform-managed and tenant BYOK tiers; `platform` uses only WAVIA keys, `byok` uses only tenant keys, and explicit `both` prefers tenant keys with platform fallback; STT Gladia→Deepgram for en/ur/ar/ms; LLM Groq→Gemini for en/ur/ar/ms with OpenAI optional; TTS Uplift→Cartesia for ur and Cartesia→ElevenLabs for en/ar/ms |
| H08 | 08 | Existing IdP, first-party auth, or API-key-only v1; admin model | Auth architecture | RESOLVED 2026-10-22 — provider-neutral external OIDC boundary for dashboard users; scoped tenant API keys for SDK/server access; short-lived session JWT and signed mint hardening remain 08C; roles are platform_admin, tenant_admin, tenant_editor, tenant_viewer, compliance_admin |
| H09 | 09 | Provide or run disposable PostgreSQL+pgvector and Redis | Required for RLS/migration/quota proof | RESOLVED 2026-10-23 — disposable PostgreSQL/pgvector and Redis verification passed; shared migration still requires separate approval |
| H10 | 10 | Knowledge sources and allowed actions | Defines the safe Phase 10 product boundary | RESOLVED 2026-10-23 — remove the undefined “hypercodes” term; implement guided common-file knowledge setup and real lifecycle actions; build secure MCP foundations with all external business systems disabled by default |
| H11 | 11 | Retention/residency, recording opt-in, human-review actions | Storage/compliance behavior | RESOLVED 2026-10-26 — privacy-first adaptive policy approved: recording is off until explicit tenant enablement and caller consent; standard defaults are 30 days for transcripts/results and 7 days for consented recordings; protected deployments require a declared storage region with no silent cross-region fallback; uncertain, sensitive, high-risk, or target-configured external actions require human approval |
| H12 | 12 | First carrier; inbound-only or outbound too; later sandbox/test number | Telephony scope/cost | RESOLVED 2026-10-26 — Telnyx first; inbound implemented first, then controlled single-call outbound; campaigns excluded; H15 retains the live number/destination/spend approval |
| H13 | 13 | Self-serve onboarding fields, billing boundary, design process | Product scope | RESOLVED 2026-10-29 — standalone Next.js Studio with a thin server-only BFF/DAL; guided plus advanced modes; FastAPI remains authoritative; usage/entitlements only with no payment; telephony readiness only until H15; Hamzi will supply visual references before 13G and must choose/provision the OIDC provider before 13B |
| H14 | 14 | Launch compliance claims and first hosting target | Operational requirements | RESOLVED 2026-11-16 — no compliance labels at launch (no HIPAA/GDPR/SOC claims; only factual descriptions of retention, redaction, consented recording, erasure, audit and data region; GDPR readiness stays roadmap); first hosting target AWS me-central-1 (UAE): containers on ECS/EC2, RDS PostgreSQL + pgvector, ElastiCache Redis, S3 recordings, AWS KMS. Nothing deployed or purchased; deploy/spend remain H15 |
| H15 | 15 | Approve publishing/deploy/live tests/calls, spend cap, destination allowlist | External and paid actions | OPEN — asked 2026-11-16 with the offline release candidate (`fb40fc6`); steps L1-L8, proposed ceilings and pre-publish decisions in `evidence/phase-15/LIVE_CERTIFICATION_PLAN.md`; nothing live has run |

## Safe information exchange

- State populated environment variable names only; do not paste values.
- Run credential-dependent commands locally and return sanitized status/timings.
- Keep allowed phone destinations in local environment, never committed files.
- Share request/session IDs and redacted logs, not tokens or raw customer transcripts.

## Stop conditions

Mark `BLOCKED — HAMZI` when an OPEN decision changes an interface/product promise; a live or paid action is next; a shared database migration is next; publishing/deployment/number purchase is next; `.github/workflows` would change; or only sensitive evidence is available.
