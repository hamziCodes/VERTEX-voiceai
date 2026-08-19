# Anti-Pattern Checklist (File 9 §5)

Cross-reference to UCVE phase fixes and verification tests.

| # | Anti-pattern | Source | UCVE fix (phase) | Verification |
|---|---|---|---|---|
| 1 | Sync blocking on event loop | v3, habiba | File 1 §3.2 async init (Phase 17) | `tests/security/test_anti_patterns.py` |
| 2 | Unbounded queues | v3, MULTI | Bounded buffers (Phase 02) | phase_tests phase_02 |
| 3 | Fire-and-forget must-await callback | multilingual | Await policy (Phase 03) | phase_tests phase_03 |
| 4 | Secrets in URLs | multilingual | WSS token not logged (Phase 07/13) | test_anti_patterns |
| 5 | Unbounded per-session resource construction | v3 | Silero pool (Phase 17) | phase_tests phase_17 |
| 6 | Invalid FSM transition applied | multilingual | Reject transition (Phase 03) | phase_tests phase_03 |
| 7 | STT language/confidence ignored | v3, all | Transcript model (Phase 05) | phase_tests phase_05 |
| 8 | Fail-open auth secrets | awaazlabs | Fail-closed HMAC (Phase 13/21) | test_anti_patterns |
| 9 | Idempotency gaps | awaazlabs | Required idempotency keys (Phase 21) | phase_tests phase_21 |
| 10 | No retry on inter-service HTTP | awaazlabs | Backoff + DLQ (Phase 25) | phase_tests phase_25 |
| 11 | Capability table mismatch | habiba | Registry validation (Phase 06) | phase_tests phase_06 |
| 12 | In-process rate limiter | habiba | Redis admission (Phase 14) | test_anti_patterns |
| 13 | No client pong / reconnect | v3, MULTI | Client duties (Phase 28) | docs/sdk/REALTIME_PROTOCOL |
| 14 | Undeclared torch in Docker | multilingual | worker-raw Dockerfile (Phase 30) | phase_tests phase_30 |
| 15 | Barge-in discards utterance | v3 | Preserve utterance (Phase 04) | phase_tests phase_04 |
| 16 | TTS split mid-code-switch | v3, MULTI | Text normalizer (Phase 16) | phase_tests phase_16 |
| 17 | No zero-retention path | all four | Redaction lifecycle (Phase 11) | test_anti_patterns |
| 18 | Single-vendor provider chain | v3, habiba | ≥2 routes (Phase 06) | test_anti_patterns |
| 19 | Single PSTN carrier only | habiba | Dual trunk (Phase 19) | phase_tests phase_19 |
| 20 | Extra SaaS for vectors/auth | MULTI | Postgres + HMAC (Phase 08/23) | phase_tests phase_08 |

Sign-off: complete manual review column in [PENTEST_READINESS.md](PENTEST_READINESS.md) before prod GA.
