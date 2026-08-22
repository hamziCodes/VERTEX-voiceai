# Universal Security Rule: Protected Key Files

## Strict Access Restriction
- **NEVER** automatically view, read, modify, copy, or parse `API KEYS VOICESDK - hamzicodes@gmai.txt` or any files matching `API KEYS*` or containing raw user secrets.
- Agents MUST ALWAYS request explicit permission from the user before reading or writing to any file containing raw API keys or secrets.
- The root `.env` file and `.env.example` are used for environment variable loading. Do NOT expose sensitive secrets in logs, artifacts, or commits.
