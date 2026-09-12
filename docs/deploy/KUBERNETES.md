# Kubernetes and Helm Scale Path

UCVE multi-service topology for scale deployments (Phase 30).

## Helm Chart Scaffold

The Helm chart skeleton is organized under `infra/helm/ucve/`:

```
infra/helm/ucve/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── control-plane-deployment.yaml
│   ├── control-plane-service.yaml
│   ├── worker-raw-deployment.yaml
│   ├── worker-raw-service.yaml
│   ├── ingress.yaml
│   └── configmap.yaml
```

> [!NOTE]
> Full Helm chart values and production cluster automated rollout are marked **[LATER]** in Phase 30. The single-node `docker compose` stack remains the primary tested Tier 0–1 install path.

## Service Split & Pod Topology

| Service | Pod Type | Replicas | Scaling Metric | Health Endpoint |
|---|---|---|---|---|
| `control-plane` | Stateless API | 2+ | CPU / Request Rate | `/health` (HTTP 8080) |
| `worker-raw` | Stateful Realtime Stream | 3+ (HPA) | Active WS Connections | `/health` (HTTP 8081) |
| `telephony-gateway` | Media Transcoder | 2+ | RTP Stream Count | `/health` (HTTP 8083) |

## Ingress & WebSocket Stickiness

- WebSocket connections to `worker-raw` (`/ws/audio`) require connection-level persistence or direct worker-affinity routing.
- Control plane REST endpoints (`/v1/*`) use standard round-robin ingress.

## Secrets Management

Never deploy raw secrets in Helm values. Use Kubernetes SealedSecrets or HashiCorp Vault / AWS KMS integration (Phase 09).
