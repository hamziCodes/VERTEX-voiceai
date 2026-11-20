# Autoscaling and Runtime Sizing Guide

Horizontal pod autoscaling (HPA) rules and telemetry metrics for UCVE (Phase 31).

## Primary Autoscaling Metric: `ucve_active_sessions`

Traditional CPU/memory metrics can be misleading for voice engines:
- Silero VAD runs short inference bursts, yielding spiky CPU.
- Memory remains relatively flat due to pre-warmed ONNX pools.

Therefore, the primary scaling signal is **`ucve_active_sessions`** (Phase 07 metric exported to Prometheus):

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: worker-raw-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker-raw
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Pods
      pods:
        metric:
          name: ucve_active_sessions
        target:
          type: AverageValue
          averageValue: "18"  # Trigger scale-out at ~72% of standard 25-session cap
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

## Scale-to-Zero Policy: NOT Supported

> [!WARNING]
> **Scale-to-zero is explicitly NOT supported.**
> Initializing PyTorch/ONNX runtime and loading the Silero VAD weights takes 1.5–2.5 seconds. For inbound PSTN calls, answer latency must be under 300 ms. Keeping a minimum of 2 warm worker replicas is mandatory across all environments.

## Connection Draining

When scaling down:
- The worker signals readiness probe failure upon SIGTERM.
- Active WebSocket sessions complete naturally.
- Worker process terminates once active session count reaches zero or grace period expires.

Implemented in Phase 14 by `core/runtime/drain.py` (`WAVIA_DRAIN_TIMEOUT_S`, default 120 s; new sessions are refused with 1013 while draining) and verified by `tests/scaling/drain_drill.py`. When the replica count changes, keep `UCVE_WORKER_REPLICAS` (or `UCVE_CLUSTER_MAX_SESSIONS`) in step so shared admission matches real fleet capacity; see `docs/runbooks/RUNBOOK_WORKER_OOM.md`.
