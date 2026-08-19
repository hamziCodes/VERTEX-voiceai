# Rollback Procedure

Container-native rollback (Phase 30). Config pin semantics (Phase 26).

## Image rollback

1. Identify last known-good image tag from deploy history.
2. Redeploy worker-raw and control-plane with previous tag:
   ```bash
   docker compose pull  # or helm rollback
   docker compose up -d control-plane worker-raw
   ```
3. Verify `/health` on both services.
4. Run smoke: mint + 1-turn mock WS (Phase 33 harness).

## Config pin behavior (Phase 26)

- **Active sessions** keep the `agent_config_version` pinned at session start until disconnect.
- Rolling back server image does **not** retroactively change in-flight session configs.
- New sessions after rollback use latest **published** pin unless explicitly versioned mint requested.

## Database migrations

- Rollback image only — do not auto-reverse migrations in prod.
- Forward-fix preferred; document in incident ticket.

## SDK compatibility

- Check `SDKVersion.min_server_version` (Phase 28) before rollback below client expectations.

## When not to rollback

- Forward fix available and migration already applied
- Rollback would reintroduce known security regression (Phase 32 checklist)

## Verification checklist

- [ ] Health checks green
- [ ] Phase 06 ≥2 routes still configured
- [ ] No secret rotation required (if rotated, update vault refs first)
