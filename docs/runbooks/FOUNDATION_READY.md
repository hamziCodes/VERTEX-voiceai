# Foundation Ready Checklist

Sign off only when every box is checked. Then set `FOUNDATION_HARDENING: COMPLETED` and `FOUNDATION_READY` in `EXECUTION_TRACKER.md` before Phase 18.

- [ ] Compose: postgres, redis, control-plane, worker-raw healthy
- [ ] Mint HMAC → JWT → WS audio round-trip with mock providers
- [ ] All H1–H5 automated tests green (`pytest tests/hardening/ -v`)
- [ ] No default crypto material accepted in `UCVE_ENV=production`
- [ ] Vault/audit/usage survive process restart (compose + migrate)
- [ ] HIPAA/GDPR gates fail closed (including override attack)
- [ ] Demo AudioWorklet client completes a local call
- [ ] Phase 18 not started

## Commands

```bash
docker compose -f infra/docker/docker-compose.yml --env-file infra/docker/.env.example up --build
python -m pytest tests/hardening/ -v
python voice_engine_plan/scripts/verify_plan_integrity.py
```

Live providers (optional nightly): `RUN_LIVE_PROVIDERS=1` with `PLATFORM_*_API_KEY` set.
