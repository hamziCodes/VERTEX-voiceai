# Human Input and Approval Register

The executor records dated answers here. No secret values belong in this file.

| ID | Needed by | Decision or information required | Why it matters | Status |
|---|---:|---|---|---|
| H01 | 00 | Reference machine, browser, and audio device for latency | Makes baselines comparable | OPEN |
| H02 | 00 | Approved non-sensitive Urdu/English fixtures | Endpoint/accuracy tuning needs representative audio | OPEN |
| H03 | 01 | Confirm latency definition and proposed live p50/p95 1,000/1,800 ms | Defines release/marketing gate | OPEN |
| H04 | 02 | Choose aggressive (~400 ms), balanced (~550–650 ms), or adaptive endpoint after evidence | Speed versus cutoff tradeoff | DEFER UNTIL EVIDENCE |
| H05 | 05 | Is Flutter in v1? Is LiveKit offered or roadmap-only? | Decides whether stubs block release | OPEN |
| H06 | 06 | May token holders override prompt/providers, or is published config authoritative? | Security and reproducibility | OPEN |
| H07 | 07 | Platform keys, BYOK, or both; required vendors per language | Credential/routing scope | OPEN |
| H08 | 08 | Existing IdP, first-party auth, or API-key-only v1; admin model | Auth architecture | OPEN |
| H09 | 09 | Provide or run disposable PostgreSQL+pgvector and Redis | Required for RLS/migration/quota proof | OPEN |
| H10 | 10 | Allowed tools/data systems; define “hypercodes” | Feature was not found and must not be invented | OPEN |
| H11 | 11 | Retention/residency, recording opt-in, human-review actions | Storage/compliance behavior | OPEN |
| H12 | 12 | First carrier; inbound-only or outbound too; later sandbox/test number | Telephony scope/cost | OPEN |
| H13 | 13 | Self-serve onboarding fields, billing boundary, design process | Product scope | OPEN |
| H14 | 14 | Launch compliance claims and first hosting target | Operational requirements | OPEN |
| H15 | 15 | Approve publishing/deploy/live tests/calls, spend cap, destination allowlist | External and paid actions | OPEN |

## Safe information exchange

- State populated environment variable names only; do not paste values.
- Run credential-dependent commands locally and return sanitized status/timings.
- Keep allowed phone destinations in local environment, never committed files.
- Share request/session IDs and redacted logs, not tokens or raw customer transcripts.

## Stop conditions

Mark `BLOCKED — HAMZI` when an OPEN decision changes an interface/product promise; a live or paid action is next; a shared database migration is next; publishing/deployment/number purchase is next; `.github/workflows` would change; or only sensitive evidence is available.
