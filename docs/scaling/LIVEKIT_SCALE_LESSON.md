# LiveKit Scale Lessons and Sovereign Worker Architecture

Architectural comparison between legacy LiveKit agent scaling and the UCVE sovereign worker model (Phase 31).

## The Habiba Deployment Bottleneck

In legacy implementations (`legacy_codebases/habiba-sdk-agent/docs/11-ARCHITECTURE.md`), deploying voice agents via WebRTC/LiveKit presented significant scaling hurdles:
- **Deployment Hard Cap:** Node deployment was constrained to at most 4 active agent deployments due to heavy WebRTC mesh peer-connection overhead and in-process thread contention.
- **In-Process Limiter Gap:** Local in-process rate limiting (AUDIT_04 §5) failed to coordinate across multiple worker pods, allowing sudden bursts of traffic to overwhelm worker memory.
- **Uncontrolled Inference:** Each worker spawned unbounded Silero instances without a pooled worker model, resulting in thread starvation and audio frame drops.

## The UCVE Sovereign Worker Resolution

UCVE decouples the real-time audio pipeline from external WebRTC SFU runtimes:

1. **Sovereign Native WebSocket Transport:**
   - Client and telephony traffic stream directly over binary WebSockets into `worker-raw`.
   - Replaces WebRTC SDP negotiation and ICE candidate overhead with deterministic frame boundaries (Phase 01).

2. **Fixed Silero VAD Pooling:**
   - Instead of per-session model instantiation, workers manage a bounded Silero VAD worker pool (`silero_pool_size` set by runtime profile).
   - In dev: 2 pool workers; in standard: 4; in high-density: 6.

3. **Cluster Admission Controller:**
   - Concurrency is governed by `SessionAdmissionController` backed by Redis counters (Phase 14 / 31).
   - Once a worker hits its `max_sessions_per_worker` cap (e.g. 25 in standard profile), requests fail closed with 503 `QUOTA_EXCEEDED` before overloading the pipeline.

4. **LiveKit as Optional Secondary Transport:**
   - LiveKit remains available as an optional client adapter (`@ucve/voice-livekit` and `worker-managed`), but is never in the critical path for sovereign deployments.
