# Audit-to-Phase Traceability

| Audit findings | Owning phase(s) |
|---|---|
| S01–S02 packaging | 05, 15 |
| A01/A03 auth and mint identity | 08 |
| A02 durable config/credentials | 06, 09 |
| F01 runtime config disconnect | 06 |
| F02 fake failover | 07 |
| F03 protocol mismatch | 05 |
| F04 injection boundary | 10 |
| F05 fake fallback success | 00, 07, 11 |
| F06 recording/call metadata | 11 |
| F07/F08 playback drain and cleanup | 04 |
| F09 RAG scaffolding | 10 |
| F10 MCP/tool scaffolding | 10 |
| F11 post-call placeholders | 11 |
| L01 timeouts | 03, 07 |
| L02 blocked ingress/queues | 02, 03 |
| L03/L04 text chunking/normalization | 03 |
| L05/L09 metric truth/schema | 01 |
| L06 buffered Uplift | 03 |
| L07 endpointing | 02 |
| L08 DSP | 03 |
| L10 cancellation | 04 |
| L11 VAD resources | 02, 14 |
| T01 missing live SIP/RTP bridge | 12 |
| T02 phone handler lifecycle | 12 |
| T03 webhook security/wiring | 12 |
| T04 call identity/replay | 12 |
| T05 secondary transport stubs | 12 |
| T06 telephony docs mismatch | 12, 15 |
| P01/P02 mock health/tool schemas | 07, 10 |
| P03 language policy | 02, 03, 06, 07 |
| P04 tenant vault | 07, 09 |
| I01 compose mode/services | 14, 15 |
| I02/I03 DB/RLS/migrations | 09 |
| I04 unsafe modes/defaults | 08, 14 |
| I05 capacity/quota leakage | 09 |
| I06 replay/token state | 08, 09 |
| I07 metering/reporting | 09 |
| I08 management stubs | 08, 10, 11, 13 |
| I09 privacy logging | 11, 14 |
| I10 retention/storage/audit | 11, 14 |
| I11 observability/readiness | 01, 14 |
| I12 image imports/assets | 15 |
| I13 broken/no-op jobs | 10, 11, 14 |
| I14 examples/docs/provider drift | 05, 07, 15 |
| Dead-code candidates | 14, 15; deletion needs separate approval |
| Three deployment models | 06–15; final acceptance in 15 |

At phase close, record commit and evidence in the phase file. New blockers are added here and assigned to the earliest safe phase; do not silently expand an active phase.
