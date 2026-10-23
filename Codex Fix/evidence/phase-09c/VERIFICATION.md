# Phase 09C Verification — Redis Admission Leases

**Date:** 2026-10-23

**Branch:** `wavia-fixv1`

**Base:** `8b6cc8c`

## Automated evidence

```text
admission/session lifecycle focused suite
39 passed, 1 warning
```

## Proven contracts

- 20 concurrent local contenders produce exactly five winners at a limit of
  five;
- reacquisition and double release are idempotent;
- expired leases reconcile without manual teardown;
- Redis acquisition uses one Lua execution for cleanup, checks, lease creation,
  and index updates;
- staging/production cannot start admission without Redis;
- control-plane mint and worker WebSocket lifecycle share the same lease.

## Next exact action

Create the 09C checkpoint commit and proceed to 09D usage and quotas. Do not
push Phase 09 without a separate instruction.
