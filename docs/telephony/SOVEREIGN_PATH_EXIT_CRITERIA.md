# Sovereign Telephony Path Exit Criteria & Architecture Specification

## Overview

Unified Core Voice Engine (UCVE) implements a **sovereign-first telephony architecture**. Inbound PSTN calls land on Telnyx webhooks, resolve tenant/agent DIDs, convert G.711 μ-law RTP audio to 16 kHz PCM16 via `DirectSIPTransport`, and feed directly into `PipelineOrchestrator` — **without requiring LiveKit**.

## Key Architecture Principles

1. **Direct SIP Sovereignty**: `DirectSIPTransport` handles native RTP packet ingestion and μ-law transcoding at the edge. LiveKit is an optional legacy adapter (`UCVE_ENABLE_LIVEKIT_SIP=false`) and is **never required**.
2. **Caller ID Context Propagation**: All telephony sessions extract E.164 `from_number` into `CallerIdContext` and attach it to session metadata for CRM extraction (Phase 21).
3. **Usage Metering**: Inbound PSTN call durations increment the `telephony_sec` meter.
4. **Fail-Closed Security**: Telnyx webhook requests require valid Ed25519 or HMAC signature verification.
