# Phase 12 Prework Readiness Evidence

**Date:** 2026-10-26

**Branch:** `wavia-fixv1`

**Scope:** documentation and implementation planning only

## Outcome

Phase 12 is split into dependency-ordered checkpoints 12A–12F. Telnyx is the first carrier. Inbound is implemented first; controlled single-call outbound follows. The selected v1 carrier boundary is Telnyx call control plus bidirectional media WebSocket. Raw SIP/RTP ownership, LiveKit, secondary carriers, and campaign dialing are outside the v1 implementation path.

No source implementation, environment file, key file, live provider, carrier endpoint, phone number, deployment, or paid service was accessed during this prework.

## Documentation read before code

- `AUDIT.md` telephony assessment T01–T06 and offline test plan
- `docs/developer/TELEPHONY_INTEGRATOR.md`
- `docs/runbooks/voice-pipeline-tuning.md`
- `docs/telephony/TRUNK_FAILOVER.md`
- `docs/runbooks/RUNBOOK_TRUNK_FAILOVER.md`
- `docs/sdk_documentation/06-api-reference.md`
- `docs/sdk_documentation/07-configuration.md`
- `Codex Fix/IMPLEMENTATION.md`, `HUMAN_INPUT.md`, `TRACEABILITY.md`, and the prior Phase 12 draft

## Current implementation map

| Area | Current evidence | Planning consequence |
|---|---|---|
| Route ownership | Control plane mounts `/v1/telephony/telnyx/webhook`; gateway also exposes unsigned `/v1/telephony/webhook/{carrier}` | 12A establishes one signed canonical endpoint and removes/protects normalization-only admission |
| Signature | Handler fails closed without key material; helper mixes carrier public-key and HMAC modes and swallows verification exceptions | 12A separates production carrier verification from test-only signing and adds strict negative vectors |
| Identity | Webhook handler and normalizer create a new session UUID for each event; missing call IDs are fabricated | 12B adds durable event replay and stable carrier-call-to-session mapping |
| DID resolution | Demo in-memory DIDs exist; database query uses `phone_number` while migration defines `did_number`; errors are swallowed | 12B replaces the demo path with async durable fail-closed lookup and ownership checks |
| Persistence | DID/trunk/call tables exist; no durable carrier-event/command lifecycle store exists; `sip_trunks` lacks the canonical Phase 18 RLS policy | 12B uses a new append-only migration for lifecycle/idempotency and canonical RLS |
| Media | `DirectSIPTransport` performs μ-law conversion/rebuffering; its network egress is only a callback | 12C builds the actual carrier media WebSocket and treats current transport as a primitive |
| Adapter truth | Telnyx adapter reports connected without network I/O and cannot receive; generic/secondary adapters contain placeholders | 12C/12E make unavailable transports fail closed |
| Pipeline | Inbound handler sends decoded frames to `process_frame_async()` and meters time but does not run the complete admitted lifecycle | 12D wires plan admission, warm providers, egress, finalization, post-call, and cleanup |
| Outbound | No authenticated call-creation service or destination/spend controls exist | 12E adds controlled single-call outbound only after inbound proof |
| Documentation | API reference advertises routes that do not exist; integrator guide describes incomplete behavior as available | 12E aligns OpenAPI, SDK docs, configuration, and runbooks with executable behavior |

## Baseline verification

Command:

```powershell
py -3.12 -m pytest voice_engine_plan/tests/phase_tests/test_phase_18_telephony_sip_base.py voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py tests/e2e/scenarios/test_telephony_inbound_e2e.py tests/e2e/test_system_endpoints_e2e.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase12-prework
```

Result: **36 passed in 2.83 seconds**, exit code 0.

Interpretation: current codec/rebuffer, normalization, route smoke, and placeholder abstraction expectations are green. These tests do not prove carrier signaling, a media socket, stable call identity, replay protection, a complete pipeline turn, outbound creation, or live operation. Several tests currently assert behavior Phase 12 must intentionally replace, such as a connection that succeeds without network media.

## Implementation prerequisites and gates

1. Finish Phase 11D before 12D closes, because telephony finalization consumes its privacy, retention, recording, and erasure contracts.
2. At 12A start, verify current official Telnyx protocol schemas and freeze sanitized fixtures. This is documentation research and does not require account credentials.
3. Use generated signing material and fake carrier/provider services for every automated checkpoint.
4. Run PostgreSQL checks only against the disposable Phase 12 database. A shared migration needs separate approval.
5. Do not place a live inbound or outbound call during implementation. Phase 15 owns the explicit number, destination allowlist, spend cap, and live-run approval.

## Human input state

H12 is resolved for implementation scope: Telnyx first; both inbound and controlled single-call outbound are product goals; inbound comes first; campaigns are excluded. H15 remains open for any live call, number purchase, deployment, or spending.

## Next exact action

Complete Phase 11D and its close gate. Then begin Phase 12A by adding failing security/contract tests from sanitized official Telnyx webhook fixtures. Do not start with carrier networking or credentials.
