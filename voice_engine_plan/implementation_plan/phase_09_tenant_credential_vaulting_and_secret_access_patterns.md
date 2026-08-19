# Phase 09: Tenant Credential Vaulting and Secret Access Patterns

## 1. Executive Summary & Core Logic

Define how provider API keys, HMAC secrets, webhook signing keys, and telephony credentials are stored, rotated, and resolved at runtime without ever reaching the browser SDK. Harvests habiba hash-only HMAC storage (`tenants.hmac_secret_hash`) and `secrets.py` / `secrets_db.py` patterns (`legacy_codebases/habiba-sdk-agent/control_plane/`). Implements envelope encryption for tenant provider credentials with audit trail hooks for every decrypt (Phase 12).

## 2. Tech Stack & Best Practices

| Choice | Justification |
|---|---|
| Application-level envelope encryption | Works on self-managed Postgres without cloud KMS day one |
| `cryptography` Fernet or AES-GCM | Standard Python crypto; key rotation support |
| Hash-only storage for HMAC verify secrets | habiba pattern — never store raw HMAC secret |
| Short-lived runtime credential cache (in-process TTL) | Reduce DB decrypt load; cleared on worker restart |

**Reference docs:** blueprint File 01 §3.6 secrets posture; habiba `mint.py` HMAC verify flow; NIST key management guidelines.

## 3. What / How / Why

- **What:** `tenant_credentials` table (`id`, `tenant_id`, `provider_id`, `credential_type`, `encrypted_blob`, `key_version`, `created_at`, `rotated_at`). `PlatformSecrets` for infra keys. API: `SecretVault.store()`, `SecretVault.resolve(tenant_id, provider_id) -> str`, `SecretVault.rotate()`. HMAC secrets: store bcrypt/argon2 hash only; verify via constant-time compare. Worker adapters receive resolved key at construction, not from env per tenant in global scope.
- **How:** **Pluggable `KMSBackend` interface:** cloud KMS (AWS KMS / GCP Cloud KMS) as default production backend; HashiCorp Vault adapter for self-hosted deployments. Envelope encryption uses KMS-wrapped DEK. **Credential cache TTL:** 5–15 min (default 10 min), configurable via `UCVE_SECRET_CACHE_TTL_SEC`; purge on rotate. **Key tiers:** platform-managed provider keys (default SMB tier) + tenant BYOK opt-in (`tenants.key_tier = 'platform' | 'byok'`). Resolve order: tenant BYOK if present, else platform key. Resolve path emits audit event via Phase 12 hook. Fail closed if secret missing.
- **Why this approach:** All four legacy repos used flat env files (AUDIT_05 gap: no Vault/KMS). Multi-tenant SaaS requires per-tenant Gladia/Gemini keys for enterprise clients. Alternative: external Vault only — defer as optional backend in Phase 30; envelope encryption ships first.

## Deliverables

- `infra/db/migrations/003_tenant_credentials.sql`
- `core/secrets/__init__.py`
- `core/secrets/vault.py` — `SecretVault` interface + Postgres implementation
- `core/secrets/envelope.py` — encrypt/decrypt helpers, key versioning
- `core/secrets/hmac.py` — hash/verify tenant HMAC secrets (mint integration)
- `core/secrets/cache.py` — TTL in-process cache with explicit invalidation on rotate
- `core/secrets/exceptions.py` — `SecretNotFoundError`, `DecryptionError`
- `core/secrets/kms/__init__.py` — `KMSBackend` protocol
- `core/secrets/kms/aws_kms.py`
- `core/secrets/kms/gcp_kms.py`
- `core/secrets/kms/vault_kms.py`
- `core/secrets/kms/local_dev.py` — `UCVE_MASTER_KEY` for local only
- `control-plane/secrets_routes.py` — admin-only rotate/revoke API stub (auth in Phase 13)

## 4. Compute & Resource Profile (if applicable)

Encrypt/decrypt: ~0.1 ms per credential on modern CPU. Cache: ~500 bytes per cached secret; cap 1000 entries per worker (~500 KB). Master key rotation requires re-wrap job — batch offline, not per-call.

## 5. Compliance Notes (if applicable)

Credentials are highest-sensitivity artifacts. Access requires audit log entry (Phase 12). HIPAA: BAA with cloud KMS if used; until then self-managed master key in HSM/VPC secret store. GDPR: credential data subject erasure on tenant delete — cascade `tenant_credentials` with tenant. Never log decrypted values; audit log records operation only.

## 6. Ambiguity Flags & Human Decision Points

None — fully deterministic. Resolved decisions:

1. **KMS backend:** pluggable interface; cloud KMS (AWS/GCP) default; Vault for self-hosted.
2. **Cache TTL:** 5–15 min (default 10 min).
3. **Key tiers:** platform-managed keys default; tenant BYOK opt-in tier.

## 7. Test Spec

- **Script:** `voice_engine_plan/tests/phase_tests/test_phase_09_credential_vaulting.py`
- **Asserts:** store/resolve round-trip; wrong master key fails decrypt; rotate invalidates cache; HMAC verify rejects wrong secret; resolve emits audit hook call; missing secret raises fail-closed error.
- **Pass threshold:** 100% vault tests; zero secret material in log capture during test run.
- **Latency target:** resolve cached < 0.5 ms; uncached decrypt < 2 ms p99.
