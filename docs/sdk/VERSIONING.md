# UCVE SDK & API Versioning Strategy

## 1. Principles of Interface Stability
To maintain reliability across sovereign voice infrastructure, the Unified Core Voice Engine follows strict semantic versioning (`MAJOR.MINOR.PATCH`).

---

## 2. Version Increment Rules

### Major Version (`vX.0.0`)
Triggered by:
- **Breaking WebSocket Realtime Event Changes**: Modifying existing event schemas, removing payload fields, or changing audio framing.
- **Breaking REST API Changes**: Removing REST endpoints or altering required request parameters.
- **Auth Protocol Invariants**: Altering HMAC signature hashing or JWT claim structures.

### Minor Version (`v1.X.0`)
Triggered by:
- **Backward-Compatible Event Additions**: New optional event types (e.g. speculative retrieval signals).
- **New Endpoints**: Adding endpoints to `/v1/` that do not alter existing contracts.
- **Provider Adapters**: Adding new STT/LLM/TTS vendor models to the registry.

### Patch Version (`v1.0.X`)
Triggered by:
- Bug fixes in audio worklets, jitter buffer tuning, connection retry loops, and internal logging fixes.

---

## 3. Deprecation Windows
- **REST API Deprecation**: Deprecated endpoints remain supported for at least **2 minor versions** with an HTTP `Deprecation` header and sunset warning log.
- **WebSocket Event Deprecation**: Deprecated realtime events remain supported for at least **1 major release cycle** with server-side translation.

---

## 4. SDK Version Manifest (`SDKVersion`)
Every UCVE SDK ships with a runtime manifest:
```json
{
  "api_version": "1.0.0",
  "event_schema_version": "1.0.0",
  "min_server_version": "0.1.0"
}
```
If an SDK connects to an incompatible server, it cleanly logs a version warning without crashing audio threads.
