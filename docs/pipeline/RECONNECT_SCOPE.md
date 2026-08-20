# UCVE Real-Time Pipeline Reconnect & Resilience Scope

## Basic Reconnect (Phase 17 Supported Scope)
- **Disconnect Behavior:** When a WebSocket connection disconnects or drops, the active worker session terminates cleanly, flushes usage metrics, records post-call records, and cleans up hot state.
- **Reconnect Behavior:** A client reconnecting issues a **new session mint** (`POST /v1/session`) to obtain a new room JWT token, initiating a new `PipelineOrchestrator` session instance.
- **Heartbeat & Resample:** `control.ping`/`control.pong` heartbeats run every 20s.

## Full Resilience & State Resumption ([LATER] Unscheduled)
- Exponential backoff reconnect loops, cross-worker session resumption, and in-flight Phase 03 FSM restore across worker node failover are deferred to `[LATER]`.
