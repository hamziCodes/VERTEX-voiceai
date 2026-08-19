# Phase 26: Self-Serve Agent Builder Domain Model

## 1. Executive Summary & Core Logic

Implement the server-side domain model, validation engine, and persistence layer for tenant-authored agent configurations — the JSON schema in File 8 §1 made executable. Primary harvest: habiba dynamic agent instantiation (`legacy_codebases/habiba-sdk-agent/worker/config.py`, `capabilities.py`, control plane agent routes AUDIT_04 §1). Generalizes habiba's language/provider matrix to domain-agnostic agents with MCP, knowledge bases, extraction schemas, telephony, and compliance refs. Validation enforces cross-phase invariants: Phase 06 ≥2 provider routes, Phase 15 RTL voice gate for Arabic, Phase 21 schema field cap, Phase 10 compliance tier rules.

Depends on Phase 08 repos, Phase 05 capability table, Phase 13 auth for CRUD, Phase 15 `validate_voice_for_publish`.

**Session config pinning:** at mint (Phase 13), load **published config version snapshot** — immune to concurrent edits mid-call. **Draft autosave:** enabled with debounce. **Template marketplace:** `[LATER]`.

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Pydantic v2 `AgentConfig` model | Mirrors File 8 §1 JSON Schema |
| JSON Schema export for Studio/API | Single source of truth |
| Optimistic versioning on publish | Safe concurrent edits |
| Draft autosave with debounce | Non-technical users lose work without it |
| Config pin at session mint | Prevents mid-call config drift |
| Validation at publish, not runtime only | Fail fast — habiba capability mismatch lesson (AUDIT_04 §6) |

**Reference docs:** blueprint File 08 §1; habiba `capabilities.py`; AUDIT_04 §1 builder surface.

## 3. What / How / Why

- **What:**
  - `AgentConfig` root: `{agent_id, tenant_id, persona, languages[], providers, tools[], mcp_servers[], knowledge_bases[], extraction_schema_id, pronunciation_lexicon[], telephony, compliance, version, published_at}`
  - **`PersonaConfig`:** `{system_prompt, greeting, voice_id, persona_isolation: true}` — DATA-framed per File 6 §1
  - **`LanguageProfileRef`:** merges Phase 15 YAML defaults with tenant overrides
  - **`ProviderConfig`:** STT/LLM/TTS/S2S priority chains — **validator rejects <2 enabled routes** per critical category/language (File 1 §3.6)
  - **`AgentConfigValidator`:** rules — Arabic RTL voice, extraction field cap, HIPAA BAA gate, MCP credential refs, telephony ≥1 trunk
  - **`AgentConfigRepo`:** draft vs published snapshots; publish creates immutable version row
  - **`DraftAutosave`:** debounced **30 s** persist of in-progress edits to `agent_config_drafts` — explicit Publish still required for runtime
  - **`SessionConfigPin`:** mint path stores `{agent_id, config_version_id, pinned_at}` on session — worker loads pinned snapshot for entire call
  - **`AgentTemplate`:** platform-provided starters (retail, clinic intake) — seed data only; **tenant-shareable marketplace `[LATER]`**
- **How:** Control-plane CRUD (`/v1/agents`) with Phase 13 RBAC. Autosave PATCH debounced from Studio (Phase 27). Publish runs full validator; failures return `StructuredError` (Phase 25). Runtime worker loads **pinned published version** at session start — never re-reads draft or newer publish mid-call.
- **Why this approach:** Habiba proved tenant-scoped agent JSON works but lacked MCP/KB generalization and mid-call stability. **Autosave required** — builder UX loses trust without it. **Config pin required** — concurrent publish during live call must not change provider chains or prompts. **Marketplace deferred** — product scope beyond MVP.

## Deliverables

- `control-plane/agents/__init__.py`
- `control-plane/agents/models/agent_config.py` — full Pydantic model
- `control-plane/agents/models/persona.py`
- `control-plane/agents/models/provider_config.py`
- `control-plane/agents/validation/validator.py` — `AgentConfigValidator`
- `control-plane/agents/validation/rules/` — modular rule modules
- `control-plane/agents/repo.py` — `AgentConfigRepo` + draft autosave
- `control-plane/agents/session_pin.py` — `SessionConfigPin`
- `control-plane/routes/agents.py` — CRUD + publish + autosave PATCH
- `infra/db/migrations/015_agent_config_versions.sql`
- `schemas/agent-config-v1.json` — exported JSON Schema
- `control-plane/agents/templates/` — platform seed templates only

## 4. Compute & Resource Profile (if applicable)

Validation: ~5–20 ms per publish. Autosave debounce: 1 write per 30 s max per active editor. Config load at mint: cached — < 2 ms from Redis/Postgres. Published row ~10–50 KB JSONB typical.

## 5. Compliance Notes (if applicable)

`system_prompt` and persona are tenant DATA — classify `pii`/`phi` by content. Published config changes audited (Phase 12 `agent_config_published`). Draft configs may contain secrets — reject inline keys, require Phase 09 refs only.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **Draft autosave:** **yes** — 30 s debounced autosave to draft table; Publish gate unchanged.
2. **Agent versioning at mint:** **pin to published version at call start** — immune to concurrent edits for session lifetime.
3. **Template marketplace:** **`[LATER]`** — platform seed templates only in v1.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_26_agent_builder_domain.py`
- **Asserts:** valid config passes validator; single-provider chain rejected; Arabic without RTL voice rejected; >max_fields extraction rejected; publish creates immutable version; mint loads pinned version not draft; concurrent publish does not affect active session pin; autosave debounce writes draft; JSON Schema export matches Pydantic model; tenant A cannot read tenant B agent.
- **Pass threshold:** 100% validation rule tests.
- **Latency target:** validate+publish < 50 ms p99.
