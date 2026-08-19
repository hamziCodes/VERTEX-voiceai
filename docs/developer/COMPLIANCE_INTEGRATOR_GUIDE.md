# Compliance Integrator Guide

Summarizes Phases 10–11 for B2B integrators. Legal review required before production HIPAA use.

## Compliance tiers (Phase 10)

| Tier | PHI in cloud LLM | BAA required | Default retention |
|---|---|---|---|
| Standard | Allowed with subprocessors | Recommended | 30 days |
| HIPAA | **Blocked until BAA signed** | **Required gate** | Configurable + legal hold |

## HIPAA BAA gate

Before enabling HIPAA tier on an agent or tenant:

1. Execute BAA with UCVE operator and listed subprocessors.
2. Acknowledge BAA checkbox in Agent Studio (Phase 27).
3. Control plane returns `HIPAA_BAA_REQUIRED` (Phase 25) if gate not satisfied.

Cloud LLM routes remain disabled until BAA status is `active` in tenant record.

## Retention and redaction (Phase 11)

- Transcripts and recordings follow tier policy; zero-retention path available.
- Post-call extraction payloads redacted before webhook dispatch.
- Deletion requests propagate to vector store and DLQ refs.

## Integrator responsibilities

- Obtain caller consent before session start.
- Host backend must not log raw audio or transcripts unless tier allows.
- Classify CRM fields you request in extraction schemas (Phase 21).

## Subprocessors

Maintain list in tenant admin settings; pointer to operator subprocessor registry (updated per release).

## Related

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — `HIPAA_BAA_REQUIRED`, `DATA_CLASSIFICATION_BLOCKED`
- Phase 12 audit trail for access logging
