# Phase 15 progress — packaging and release qualification

**Branch:** `wavia-fixv1`
**Spec:** `Codex Fix/phases/15-packaging-release-qualification.md`, executed
task by task (no sub-phases, no new plan files).
**Status:** offline qualification complete; H15 (live, publish, deploy,
spend) awaits Hamzi.

## Tasks

| # | Task | Outcome | Commits |
|---|---|---|---|
| 1 | Containers build from a clean checkout | All five images rendered from one template: digest-pinned base, hash-pinned lock export, every package and runtime asset, import check, non-root. Before: control plane crashed on import, worker-managed lacked httpx, no image had profiles/migrations, no psycopg_pool | `1a6f6a2` |
| 2 | Pin dependencies; vulnerability and licence scan | `requirements/runtime.txt` from `uv.lock` with `--check`; 8 advisories fixed; licence report (psycopg LGPL for sign-off) | `5f5fe9f` |
| 3 | Build and install packages; run quickstarts | Wheel, sdist, npm tarball installed into isolated consumers; quickstarts get agent audio from the release images | `4fb0aa8`, `cc92722` |
| 4 | Exclude legacy, caches, secrets from artifacts | Root `.dockerignore`; `.gitattributes` for LF scripts/SQL | `1a6f6a2`, `a8b4e96` |
| 5 | Docs from runtime contracts | `openapi.yaml` generated (71 routes, was 4) and served from the app; quickstart and API references corrected; nonexistent endpoints removed | `87ff3da`, `3cefc0e` |
| 6 | Drills | Upgrade, rollback, Redis restart, SIGKILL restart, database network loss — all pass after the fixes they exposed | `fb40fc6` and fixes below |
| 7 | Offline matrix and latency corpus | 1171 offline; 61+1+1 disposable-service tests; privacy proof; latency corpus recorded | `b941558` |
| 8 | Qualify SDK / managed / self-serve separately | `QUALIFICATION.md` with checklists and "not included" lists | — |
| 9 | Live certification commands and cost limits | `LIVE_CERTIFICATION_PLAN.md`; `live_certification.sh` refuses without per-step approval; not run | `dd66f09` |
| 10 | Release notes, rollback, compatibility, handoff | `docs/release/RELEASE_NOTES_0.1.0-rc1.md`, `ROLLBACK.md`, `COMPATIBILITY.md`, `SUPPORT_HANDOFF.md` | close gate |
| 11 | H15 approvals | Asked; see below | — |

## Defects found by qualifying (each with a failing-first regression test)

1. Log redaction broke every uvicorn access-log line in containers (`3990289`).
2. SDKs retried sessions the worker had already rejected, masking 4401 as HTTP 403 (`cc92722`).
3. The migration CLI failed on Windows (`245d941`).
4. The provider ping script put the Gemini key in a URL (`e971986`).
5. The telephony gateway reported ready with a malformed Telnyx key (`5e0687b`).
6. A Redis outage was reported as a nonce replay / invalid token; revocations were silently dropped (`6d050bd`).
7. Migration checksums depended on the checkout's line endings (`a8b4e96`).
8. Redis clients had no timeouts or stale-connection checks (`15b44a9`).
9. Losing the database froze the control plane for ~15 s and mint returned a plain 500 after 30 s; the worker reported DB/admission outages as 4401 or a normal 1000 (`aef39bf`).

## Findings for Hamzi

- **H15 decisions** (`LIVE_CERTIFICATION_PLAN.md`): approve L1–L7 individually; package names (`ucve` → Wavia?) and SDK version before any publish; add a LICENSE; sign off psycopg's LGPL.
- **No live latency runner exists**: the offline corpus measures pipeline overhead only; a live runner is Stage 3 work and needs FLEURS licence acceptance (H02).
- **Network on this machine** had DNS timeouts during builds; a no-cache control-plane build took 16 minutes, almost all downloads.
- Unchanged from Phase 14: post-call intelligence provider, webhook-target management, Phase 13 exit 8 screenshots, 8 delete-proposed items.
- `D:\d` (≈14 MB, stray SDK copies from a mis-set shell variable) could not be deleted by the agent's safety check; please remove it.
