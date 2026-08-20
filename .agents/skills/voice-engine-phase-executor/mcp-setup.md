# MCP Configuration & Installation Guide — Voice Engine Build

In **Antigravity**, core operations (terminal commands, pytest, integrity verification, file reading, and file writing) are handled **natively** by built-in tools. No extra MCP servers are required for Phases 00–07.

---

## Current Status: Clean Baseline (No MCPs Required for Phases 00–07)

* **Phases 00–07**: 100% native execution via Antigravity tools.
* **Workspace Config**: `.agents/mcp_config.json` is set to `{ "mcpServers": {} }`.

---

## Future MCP Integration: PostgreSQL (Phase 08+)

Starting in **Phase 08** (Multi-Tenant Core Data Model & PostgreSQL Schemas), you can optionally add PostgreSQL MCP for interactive DB schema inspection.

### Manual Installation & Setup Instructions (When Reaching Phase 08)

1. **Ensure Node.js is installed** (`npx` must be available in PATH).
2. **Ensure PostgreSQL is running** locally or on your target host.
3. **Update `.agents/mcp_config.json`**:

```json
{
  "mcpServers": {
    "postgres": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-postgres",
        "postgresql://localhost:5432/ucve_dev"
      ]
    }
  }
}
```

---

## MCP Lifecycle Summary

| Phases | Needed MCPs | Action Required |
|--------|-------------|-----------------|
| **00–07** | None (Native tools) | None |
| **08–14** | PostgreSQL (Optional) | Start local Postgres, add `postgres` config to `.agents/mcp_config.json` |
| **15–35** | None / Postgres | Keep active as needed for migrations |
