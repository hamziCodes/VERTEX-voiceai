# Phase 19: Telephony Abstraction and Secondary Trunk Readiness

## 1. Executive Summary & Core Logic

Generalize telephony behind `BaseTelephonyTransport` and `SIPTrunkConfig` so Telnyx+DirectSIP (Phase 18 sovereign path) and optional LiveKit convenience (Phase 18) are adapters, not hardcoded paths. Add **configurable** second-trunk failover before calling PSTN "production-ready" (blueprint File 07 §4.1, File 01 §3.6 kill-switch). **Default:** single trunk sufficient for dev/staging; second trunk is **configurable failover**, not mandatory at startup. No Twilio Media Streams implementation — interface stub only.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| `SIPTrunkConfig` with `primary`/`secondary` roles | File 07 §4.1 |
| Failover parallel to Phase 06 router | Consistent resilience model |
| Trunk credentials via Phase 09 vault refs | Never inline in config |
| Provider-neutral webhook normalizer | Map Telnyx/Twilio events → internal `TelephonyEvent` |
| Interface-first for unbuilt providers | Matches provider-agnostic principle (Phase 05 pattern) |

**Reference docs:** blueprint File 07 §4; habiba `tenant_portal_api/telephony_config.py`.

## 3. What / How / Why

- **What:**
  - `BaseTelephonyTransport`: `connect`, `send_audio`, `receive_audio`, `hangup`, `health_check`
  - `SIPTrunkConfig`: `{provider, credentials_ref, webhook_public_key, priority, role}` — **single trunk valid**; secondary optional
  - Adapters: `TelnyxDirectSIPAdapter` (Phase 18 wrap), `TelnyxLiveKitAdapter` (optional), `GenericPTAAdapter` (config-ready), `TwilioSIPAdapter` (config stub)
  - `TelephonyFailoverRouter`: if primary trunk health check fails **and** secondary configured, route new calls to secondary; single-trunk tenants fail closed on primary outage (documented)
  - **`TwilioMediaStreamTransport`:** ABC + config types only — **no implementation**; `[LATER]` per provider-agnostic stub pattern
  - **`DirectSIP outbound`:** `[LATER]` — inbound remains v1 priority; skeleton method signatures only
  - Unified `TelephonyEvent` enum: `call_started`, `call_answered`, `call_ended`, `dtmf`
- **How:** Agent config (Phase 08 JSONB) lists trunk priority chain analogous to Phase 06 provider chains. `minItems: 1` for dev; production docs recommend ≥2 trunks (File 01 §3.6) but **not startup-enforced**. Inbound: webhook normalizer → resolver → Phase 17 session. Health checks: periodic OPTIONS/ping per configured trunk. Phase 12 audit on trunk failover.
- **Why this approach:** File 01 §3.6 forbids single-carrier hostage in production guidance, but mandating two trunks at dev startup blocks local work. Habiba is Telnyx-only (grep twilio=0). Twilio stub preserves extension point without over-building for unused provider. Alternative: mandatory dual-trunk at boot — rejected for dev ergonomics.

## Deliverables

- `telephony-gateway/base.py` — `BaseTelephonyTransport`, `TelephonyEvent`
- `telephony-gateway/trunk_config.py` — `SIPTrunkConfig`
- `telephony-gateway/failover.py` — `TelephonyFailoverRouter`
- `telephony-gateway/adapters/telnyx_direct_sip.py`
- `telephony-gateway/adapters/telnyx_livekit.py` — optional wrap
- `telephony-gateway/adapters/generic_pta.py` — config stub
- `telephony-gateway/adapters/twilio_sip.py` — config stub
- `telephony-gateway/adapters/twilio_media_stream.py` — **interface stub only**
- `telephony-gateway/webhook_normalizer.py`
- `infra/db/migrations/010_sip_trunks.sql`
- `docs/telephony/TRUNK_FAILOVER.md` — single vs dual trunk guidance

## 4. Compute & Resource Profile (if applicable)

Failover router overhead: negligible. Direct SIP media path avoids LiveKit ~20–40 ms — target for latency-sensitive tenants. Second trunk health probe: 1 request/min/trunk when configured — minimal.

## 5. Compliance Notes (if applicable)

Each trunk provider is Phase 10 subprocessor. Call metadata may cross trunk failover — ensure caller ID and recording URI remain consistent in session record (Phase 20). Cross-border routing flag per trunk region for GDPR.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Second trunk:** **single trunk default**; second trunk **configurable failover**, not mandatory at startup.
2. **DirectSIP outbound:** defer `[LATER]`; inbound priority.
3. **Twilio Media Streams:** **interface stub only** — no real implementation in this phase.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_19_telephony_abstraction.py`
- **Asserts:** single-trunk config validates; two-trunk config validates; primary failure routes to secondary when configured; single-trunk primary failure surfaces explicit error; DirectSIP adapter produces 16 kHz frames to pipeline mock; webhook normalizer maps Telnyx sample payload; TwilioMediaStreamTransport is abstract/uninstantiable stub; missing credentials fail closed.
- **Pass threshold:** failover simulation passes when secondary configured; single-trunk mode passes without secondary.
- **Latency target:** failover decision < 10 ms (excluding call setup).
