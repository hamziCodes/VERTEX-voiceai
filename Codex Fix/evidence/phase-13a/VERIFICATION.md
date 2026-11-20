# Phase 13A Verification Evidence

Date: 2026-10-30

Branch: `wavia-fixv1-phase13a`

Base commit: `5c1c72d`
Status: **PASSED — commit/push confirmation pending**

## Scope completed

- Durable external identity mapping, workspace membership, invitations, onboarding, and entitlements.
- OIDC identity-only authentication with tenant role resolution from durable membership state.
- Workspace, member, invitation, onboarding, entitlement, provider catalog, and template APIs.
- Tenant-scoped conversation history/detail/intelligence APIs with deterministic cursor pagination.
- Telephony policy/readiness APIs that perform no carrier-side action.
- Optimistic agent draft revisions, stale-write protection, structured validation, immutable versions, and restore-to-draft.
- Quota-bound API-key lifecycle with one-time plaintext display.
- Encrypted provider-credential lifecycle with metadata-only responses and cache-invalidating revocation.
- Fresh-schema disposable integration test covering RLS, invitations, draft concurrency, credential redaction, API-key redaction, and conversation pagination.

## Fresh offline evidence

### Phase 13A focused gate

```powershell
$env:RUN_LIVE_PROVIDERS='0'
$env:RUN_LIVE_DB_TESTS='0'
$env:RUN_LIVE_REDIS_TESTS='0'
$env:UCVE_ENV='test'
py -3.12 -m pytest tests/studio tests/auth tests/agents tests/providers tests/rag tests/post_call tests/telephony -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13a
```

Result: **313 passed in 4.39s**.

### Repository-wide forced-offline gate

```powershell
py -3.12 -m pytest -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13a-full
```

Result: **965 passed, 14 skipped, 2 warnings in 11.99s**. The two warnings are the existing short-HMAC test-fixture warnings in `tests/hardening/test_h1_auth_crypto.py`; no new warning class was introduced.

### Migration and integration-test contract

```powershell
py -3.12 -m pytest tests/db/test_phase13_studio_migration.py tests/db/test_phase09_database.py tests/db/test_phase13_live_integration.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13a-db-offline
```

Result: **10 passed, 1 skipped in 0.23s**. The skip is intentional because the disposable database flag was off.

### Static and security gates

- Changed-file Ruff: **passed**.
- Python compileall for changed packages/tests: **passed**.
- `git diff --check`: **passed**.
- `.github/workflows` protected-path scan: **clean**; no workflow changes.
- Credential-pattern filename scan: one candidate, reviewed as the fake string `expired-invitation-token` in an offline test fixture; no environment file or raw key file was read.
- API-key and secret-vault security regression: **31 passed in 0.47s**.
- Generated literal `%SystemDrive%` pytest artifact was verified inside the isolated worktree and removed.

## Disposable PostgreSQL/Redis gate

Executed from the isolated Phase 13A worktree. The command created only local disposable containers, made no provider request, and placed no call. The `finally` block removed the containers, network, and volumes.

```powershell
$env:PHASE09_DB_PASSWORD=[guid]::NewGuid().ToString('N')
$compose='infra/docker/docker-compose.phase09-test.yml'
$testExit=1
try {
    docker compose -f $compose up -d --wait
    $env:DATABASE_URL="postgresql://phase09:$($env:PHASE09_DB_PASSWORD)@127.0.0.1:55432/phase09"
    $env:REDIS_URL='redis://127.0.0.1:56379/0'
    $env:RUN_LIVE_DB_TESTS='1'
    $env:RUN_LIVE_REDIS_TESTS='1'
    $env:RUN_LIVE_PROVIDERS='0'
    $env:UCVE_ENV='test'
    py -3.12 -m pytest tests/db/test_phase13_live_integration.py tests/metering/test_phase09_live_redis.py -q -p no:cacheprovider --basetemp hamza_local/pytest-phase13a-disposable
    $testExit=$LASTEXITCODE
}
finally {
    docker compose -f $compose down --volumes
    Remove-Item Env:PHASE09_DB_PASSWORD,Env:DATABASE_URL,Env:REDIS_URL,Env:RUN_LIVE_DB_TESTS,Env:RUN_LIVE_REDIS_TESTS -ErrorAction SilentlyContinue
}
if ($testExit -ne 0) { exit $testExit }
```

Result: **2 passed in 19.24s**.

Post-run cleanup verification:

- `docker compose ... ps -a`: no containers.
- Compose-labelled volume query: no volumes.
- Compose-labelled network query: no network.
- All three cleanup verification commands exited `0`.

## Limitations and stop gate

- No external OIDC provider has been selected or configured. That decision is required before Phase 13B authentication integration.
- The standalone Studio frontend has not been scaffolded; it begins only after Phase 13A is verified and approved.
- No live provider request, carrier action, phone call, deployment, package publication, or paid operation occurred.
- No Phase 13A commit or push has been performed. Hamzi's explicit confirmation remains required.

Next exact action: review the Phase 13A gate and explicitly authorize or decline the clean commit/push. Do not start Phase 13B before that decision.
