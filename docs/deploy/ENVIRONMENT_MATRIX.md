# Environment Matrix

Variable ownership across UCVE services (Phase 30).

## Tiers

| Aspect | dev | staging | prod |
|---|---|---|---|
| Install | docker compose | compose overlay | compose or K8s |
| Providers | mock OK | sandbox keys | production keys |
| OTel | off | on | on |
| HIPAA BAA | optional | required for HIPAA test tenants | enforced |
| Provider routes | ≥1 mock | ≥2 sandbox | ≥2 production (Phase 06) |

## Service variables

| Variable | control-plane | worker-raw | telephony-gateway | Notes |
|---|---|---|---|---|
| `DATABASE_URL` | ✓ | ✓ | ✓ | Postgres TLS in prod |
| `REDIS_URL` | ✓ | ✓ | ✓ | AUTH in prod |
| `UCVE_RUNTIME_PROFILE` | — | ✓ | — | Phase 31 |
| `UCVE_ENABLE_LIVEKIT` | ✓ | ✓ | optional | default `false` |
| `OTEL_EXPORTER_ENABLED` | ✓ | ✓ | ✓ | Phase 07 |
| `UCVE_TENANT_API_KEY` | vault ref | — | — | Phase 09 |
| Secrets inline | **never** | **never** | **never** | vault/sealed secrets |

## Promotion checklist

- [ ] Phase 33 TEST_MATRIX green on staging
- [ ] Phase 32 PENTEST_READINESS sign-off
- [ ] ≥2 provider routes verified
- [ ] No secrets in git or compose committed files

## Related

- [COMPOSE_QUICKSTART.md](COMPOSE_QUICKSTART.md)
- [../developer/env/.env.example](../developer/env/.env.example)
