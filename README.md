# Wavia Voice AI

> Sovereign real-time voice infrastructure engineered for sub-second, resilient voice AI agent operations.

Wavia (powered by the Unified Core Voice Engine architecture) is a high-performance, modular, multi-tenant voice AI platform providing duplex streaming, voice activity detection, dynamic provider failover, and carrier-grade telephony integration.

## Architectural References

- **Architecture Blueprints**: See [`docs/blueprint/`](docs/blueprint/README.md) for system topology, core FSM, provider abstractions, multilingual engine, and telephony specifications.
- **Execution Plan**: See [`voice_engine_plan/`](voice_engine_plan/README.md) for the 36-phase deterministic build plan, test suite, and operational trackers.
- **Costing & Commercial Models**: See [`costing/`](costing/) for unit economics, infra sizing, and client proposal tiers.

## Monorepo Layout

- `core/`: Sovereign engine kernel, canonical frame contracts, session state machines, and provider adapters.
- `control_plane/`: Management APIs, agent builder services, tenant RBAC, and telemetry dispatch.
- `worker_raw/`: Low-latency audio pipeline workers, VAD/STT/LLM/TTS orchestration, and transport streaming.
- `telephony_gateway/`: SIP trunking adapters (Twilio, Telnyx) and carrier webhooks.
- `sdk/`: Client SDKs for TypeScript/React, Python, and mobile platforms.
- `examples/`: In-browser developer console and interactive voice testing apps.
- `infra/`: Scaling profiles, Docker compositions, and database migrations.
- `legacy_codebases/`: Harvested reference codebases (read-only).
