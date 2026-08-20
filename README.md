# Unified Core Voice Engine (UCVE)

Sovereign real-time voice infrastructure engineered for sub-second, resilient voice AI agent operations.

## Architectural References

- **Architecture Blueprints**: See [`docs/blueprint/`](docs/blueprint/README.md) for system topology, core FSM, provider abstractions, multilingual engine, and telephony specifications.
- **Execution Plan**: See [`voice_engine_plan/`](voice_engine_plan/README.md) for the 36-phase deterministic build plan, test suite, and operational trackers.

## Monorepo Layout

- `core/`: Sovereign engine kernel, canonical frame contracts, session state machines, and compliance boundaries.
- `control-plane/`: Management APIs, agent builder services, tenant RBAC, and telemetry dispatch.
- `worker-raw/`: Low-latency audio pipeline workers, VAD/STT/LLM/TTS orchestration, and transport streaming.
- `infra/`: Scaling profiles, Docker compositions, and database migrations.
- `legacy_codebases/`: Harvested reference codebases (read-only).
