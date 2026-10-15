# Repository Structure Decisions

This is the C03 package-boundary map. It separates Python import names from distribution, Compose, and Docker service names so a naming cleanup does not break valid contracts.

| Path or name | Role | Decision | Evidence / risk |
|---|---|---|---|
| `core/` | Shared runtime/domain Python package and workspace project | Keep | Imported throughout runtime; included in root wheel and workspace |
| `control_plane/` | Canonical Python package; distribution name `control-plane` | Keep | Root wheel, workspace, Dockerfile, tests, and imports use it |
| `worker_raw/` | Canonical raw WebSocket worker package; distribution name `worker-raw` | Keep | Root wheel, workspace, Dockerfile, tests, and imports use it |
| `telephony_gateway/` | Canonical telephony Python package; distribution name `telephony-gateway` | Keep | Root wheel/workspace and Docker entry point use it |
| `post_call/` | Canonical post-call Python package; distribution name `post-call` | Keep | Root wheel/workspace and worker/control-plane images include it |
| `control-plane/` | Hyphenated compatibility path | Keep for now | Phase 00 layout contract requires the directory; shim delegates to `control_plane` |
| `worker-raw/` | Hyphenated compatibility path | Keep for now | Phase 00 layout contract requires it; file explicitly marks canonical `worker_raw/` |
| `worker_managed/` | Optional LiveKit worker | Keep | `worker-managed.Dockerfile` copies and starts it; incomplete does not mean dead |
| `worker_jobs/` | Background job modules | Keep pending C05 | Audit found no-op/broken jobs, but they represent promised operational work and require capability decisions |
| `sdk/` | Separately packaged client SDKs | Keep separate | Python SDK has independent metadata and Python compatibility range |
| `agent-studio/` | Agent-builder specification surface | Keep | Phase tests reference it; implementation completeness is a production-plan issue |
| `schemas/` | Shared agent configuration contract | Keep | Public/config contract, not clutter |
| `infra/` | Docker, database, observability, and deployment material | Keep | Active Docker and phase-test consumers |
| `voice_engine_plan/` | Original implementation plan and executable phase tests | Keep | Root pytest configuration collects these tests |
| `legacy_codebases/` | Comparison/reference implementations | Keep outside packages | Requested for latency comparison; excluded from pytest recursion and root wheel package list |
| `docs/archive/` | Historical decision/audit evidence | Keep | Reference evidence; archive location already communicates status |
| `examples/`, `scripts/`, `costing/` | Supporting developer and planning assets | Keep pending C05 item review | Small, named surfaces; no structural benefit from moving the directories |
| `.cursor/`, `.qoder/`, `.superpowers/` | Ignored local tool state | Keep locally | Active/possibly useful state; not part of Git or release artifacts |
| `hamza_local/clean_codebase/` | Ignored recovery quarantine | Keep locally | Required by this cleanup; never packaged or committed |

## Naming decision

Python import directories use underscores because Python module names cannot be imported normally with hyphens. Python distribution names and Docker Compose service names use hyphens, which is conventional and already referenced by tests and deployment files. Renaming these to make every layer visually identical would break valid package/service contracts without improving runtime behavior.

C04 therefore has no safe broad rename to perform. Any future removal of `control-plane/` or `worker-raw/` must first replace the explicit Phase 00 layout contract. Public SDK import names, service names, image names, ports, and URLs require a migration plan and Hamzi's approval.

## Structural defects found

1. `uv.lock` is not valid for the installed UV version: `uv lock --check` reports that the lock file lacks required metadata. Regenerating it may resolve/download dependency metadata, so it belongs in a separately approved dependency/packaging task.
2. Root `tool.uv.dev-dependencies` is deprecated; UV requests `dependency-groups.dev`.
3. The production-secret guard test fails in isolation because importing `core.runtime.env` loads the root `.env` before the assertion. The test deletes process variables first, then module import repopulates them. This is an auth/config correctness defect, not a directory-layout failure, and should be fixed with the production security work.
4. `core/latency` has 19 pre-existing Ruff findings. They are style/unused-import debt and should be fixed in a focused, tested change rather than mixed into dead-code removal.
5. The ignored `infra/docker/.env` exists locally. It is configuration, so this cleanup does not inspect further, copy, move, or record its values. The tracked `infra/docker/.env.example` remains the template.

## C03 verification evidence

- Canonical package imports passed under system Python 3.12.
- Phase 00 latency suite remained 15 passed after C01/C02.
- Targeted package/layout/deployment set: 17 passed, 1 existing production-secret guard failure.
- Targeted collection: 70 tests collected after duplicate test paths were removed.
- Canonical `tests/latency` Ruff check passed.
- UV 0.13.1 parsed project metadata but rejected the existing lock file as invalid.

No package, public import, Compose service, Dockerfile, port, or URL was renamed in C03.
