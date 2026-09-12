# UCVE Agent Studio — Outbound Campaign UI Deferral Notice

## 1. Architectural Scope Decision
In Phase 18 and Phase 19 (Telephony/SIP Base and Abstraction), outbound calling campaigns, predictive dialing algorithms, and batch contact list ingestion were classified as `[LATER]` to prioritize sovereign inbound reliability and low-latency stream orchestration.

---

## 2. Studio UI Impact
- **No Outbound Wizard**: The Agent Studio v1 does not include an outbound dialer or campaign scheduler.
- **No Contact List Uploaders**: File dropzones for CSV phone lists are omitted from screen inventory (`SCREEN_INVENTORY.md`).
- **Telephony Screen Scope**: Screen `SCR-09` (`/agents/:id/telephony`) is strictly focused on:
  1. Inbound DID number mapping.
  2. Inbound SIP URI sovereign registration.
  3. Direct routing to agent persona.

---

## 3. Future Implementation Pointer
Outbound campaign builder interfaces will be designed in a post-v1 phase once Telnyx and Direct SIP outbound call initiation primitives and regulatory compliance gates (STIR/SHAKEN, TCPA, DNC list scrubbing) are certified in the telephony gateway.
