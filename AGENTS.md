# Workspace Agent Guidelines & Security Rules

## Universal Security & Key Restrictions
- **STRICT DIRECTIVE**: Agents must **NEVER** read, view, or modify `API KEYS VOICESDK - hamzicodes@gmai.txt` or any raw API key files without explicit permission from the user. Always ask the user first.
- **Git Safety**: All secret files (`.env`, `API KEYS*`) are gitignored and must never be staged or committed.

## Environment File Location
- The `.env` configuration file resides directly in the repository root: `d:\PROJECTS\PASSION PROJECTS\VERTEX_voiceai\.env`.
- Copy `.env.example` to `.env` in the root directory to configure environment variables.
