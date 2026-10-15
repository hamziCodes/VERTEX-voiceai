# Execution Tracker

This is the authoritative progress record. Update it only from evidence: implementation commit(s), verification command/result, and completed human gate where required.

| Phase | Status | Implementation evidence | Automated verification | Human gate/evidence | Notes |
|---:|---|---|---|---|---|
| 00 | IMPLEMENTED — AWAITING HUMAN INPUT | `wavia-fixv1`; Phase 00 commit pending | 11 focused passed; Ruff/compile/diff checks passed; existing suite 64 passed/3 pre-existing failed; 42-sample artifact | H01/H02 open; real-language acceptance blocked | Technical harness complete; do not start Phase 01 yet |
| 01 | NOT STARTED | — | — | H03 open | Metric truth |
| 02 | NOT STARTED | — | — | H04 after A/B | Listening/STT latency |
| 03 | NOT STARTED | — | — | Provider/listening approval later | First audio/DSP |
| 04 | NOT STARTED | — | — | Local listening at exit | Interruption/lifecycle |
| 05 | NOT STARTED | — | — | H05 open | Protocol/SDK |
| 06 | NOT STARTED | — | — | H06 open | Session compiler |
| 07 | NOT STARTED | — | — | H07 open | Providers/credentials |
| 08 | NOT STARTED | — | — | H08 open | Auth/tenancy |
| 09 | NOT STARTED | — | — | H09 open | Data/migrations/quota |
| 10 | NOT STARTED | — | — | H10 open | RAG/tools/hypercodes |
| 11 | NOT STARTED | — | — | H11 open | Post-call |
| 12 | NOT STARTED | — | — | H12 open; live call separate | Telephony |
| 13 | NOT STARTED | — | — | H13 open | Studio |
| 14 | NOT STARTED | — | — | H14 open | Operations/compliance |
| 15 | NOT STARTED | — | — | H15 open | Release qualification |

## Evidence format

For each completed phase, replace dashes with:

- implementation commit SHA(s) and a one-line scope;
- exact command(s), date, exit code, passed/failed/skipped counts, and artifact paths;
- latency/security/storage measurements where applicable;
- Hamzi's dated decision or acceptance reference without secret values;
- known limitations and any accepted risk ID.

## Per-task execution discipline

Every implementation checkbox in a phase expands into this cycle:

1. Name the exact files and interface being changed.
2. Write a focused failing test or capture the failing baseline.
3. Run it and record the expected failure.
4. Implement the smallest coherent change.
5. Run the focused test and related regression set.
6. Inspect diff and secret/privacy/fake-success risks.
7. Commit a reviewable unit, preserving unrelated user changes.

At phase end, run its complete verification block and the scan in `VERIFICATION.md`. If Hamzi runs the command, the phase stays `VERIFICATION NEEDED` until sanitized evidence is recorded.
