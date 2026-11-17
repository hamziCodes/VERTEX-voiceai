"""The production job catalogue: what the jobs runner schedules and why.

Each entry is either wired to a real durable repository or disabled with a
reason that the runner reports. Jobs that were previously no-ops or fake
successes (``quota_monthly_reset``, ``quota_stale_sweeper``,
``dlq_retry_sweeper`` over the in-memory DLQ) are deliberately absent; see
the Phase 14 cleanup classification.
"""

from __future__ import annotations

import os
import socket
import uuid
from typing import Any

from core.alerts.models import AlertCode, AlertSeverity
from core.observability.metrics import ucve_job_queue_depth
from post_call.intelligence_providers import post_call_disabled_reason
from worker_jobs.scheduler import JobSpec, drain

DRAIN_BATCH = 25

# Durable job tables and the state that means "gave up".
QUEUE_TABLES: dict[str, tuple[str, str]] = {
    "post_call_intelligence": ("post_call_jobs", "dead_letter"),
    "webhook_delivery": ("webhook_deliveries", "dead_letter"),
    "privacy_deletion": ("privacy_deletion_jobs", "dead_letter"),
    "knowledge_ingestion": ("knowledge_ingestion_jobs", "failed"),
}


def default_runner_id() -> str:
    return f"jobs-{socket.gethostname()[:40]}-{uuid.uuid4().hex[:8]}"


async def observe_queues(database: Any, alerts: Any | None) -> int:
    """Publish per-state depth for every durable queue; alert on dead letters."""
    observed = 0
    async with database.platform_transaction() as conn:
        for family, (table, terminal) in QUEUE_TABLES.items():
            cursor = await conn.execute(
                f"SELECT state, count(*) FROM {table} GROUP BY state"  # noqa: S608 - fixed table names
            )
            counts = {str(row[0]): int(row[1]) for row in await cursor.fetchall()}
            for state in ("queued", "running", "retry_wait", "succeeded", terminal):
                ucve_job_queue_depth.labels(job=family, state=state).set(
                    counts.get(state, 0)
                )
            observed += 1
            if alerts is None:
                continue
            key = f"job_dead_letter:{family}"
            dead = counts.get(terminal, 0)
            if dead:
                await alerts.raise_safely(
                    alert_key=key,
                    code=AlertCode.JOB_DEAD_LETTER,
                    severity=AlertSeverity.ERROR,
                    summary=f"{family.replace('_', ' ').capitalize()} has jobs that "
                    "exhausted their retries.",
                    facts={"job": family, "count": dead, "state": terminal},
                )
            else:
                await alerts.resolve(key, resolved_by="jobs-runner")
    return observed


def build_job_specs(
    database: Any | None,
    *,
    runner_id: str,
    alerts: Any | None = None,
    post_call_providers: tuple[Any, Any] | None = None,
) -> list[JobSpec]:
    """Build the scheduled jobs for this process.

    ``post_call_providers`` is ``(extraction_provider, summary_provider)`` from
    ``post_call.intelligence_providers.build_post_call_providers``; ``None``
    disables the intelligence queue with the reason it gives.
    """
    if database is None:
        reason = "no database configured"
        return [
            JobSpec(name, 5.0, None, disabled_reason=reason)
            for name in (
                "post_call_intelligence",
                "webhook_delivery",
                "knowledge_embedding",
                "privacy_deletion",
                "retention_enqueue",
                "queue_observer",
            )
        ]

    specs: list[JobSpec] = []

    # 1. Post-call intelligence (extraction, summary, review routing).
    if post_call_providers is None:
        specs.append(
            JobSpec(
                "post_call_intelligence",
                5.0,
                None,
                disabled_reason=post_call_disabled_reason(),
            )
        )
    else:
        from core.db.repos.post_call_repo import PostgresPostCallRepository
        from post_call.extraction.service import ExtractionService
        from post_call.jobs.repository import PostgresPostCallJobRepository
        from post_call.summarization.service import SummarizationService
        from post_call.webhook.repository import PostgresWebhookRepository
        from post_call.worker import PostCallJobWorker

        extraction, summary = post_call_providers
        post_call_worker = PostCallJobWorker(
            call_repository=PostgresPostCallRepository(database),
            job_repository=PostgresPostCallJobRepository(database),
            extraction_service=ExtractionService(provider=extraction),
            summarization_service=SummarizationService(provider=summary),
            worker_id=runner_id,
            webhook_repository=PostgresWebhookRepository(database),
        )

        async def _post_call() -> int:
            return await drain(post_call_worker.run_once, DRAIN_BATCH)

        specs.append(JobSpec("post_call_intelligence", 2.0, _post_call))

    # 2. Signed tenant webhook delivery (same vault configuration as the
    #    control plane, which stores the tenant signing secrets).
    from core.secrets.repository import PostgresSecretRepository
    from core.secrets.vault import SecretVault
    from post_call.webhook.dispatcher import (
        VaultWebhookSecretResolver,
        WebhookDispatcher,
    )
    from post_call.webhook.repository import PostgresWebhookRepository
    from post_call.webhook.service import WebhookDeliveryWorker

    # Same construction as the control plane lifespan; the async Postgres
    # repository satisfies the vault's repository contract at runtime.
    vault = SecretVault(
        repository=PostgresSecretRepository(database)  # type: ignore[arg-type]
    )
    webhook_worker = WebhookDeliveryWorker(
        repository=PostgresWebhookRepository(database),
        dispatcher=WebhookDispatcher(secret_resolver=VaultWebhookSecretResolver(vault)),
        worker_id=runner_id,
    )

    async def _webhooks() -> int:
        return await drain(webhook_worker.run_once, DRAIN_BATCH)

    specs.append(JobSpec("webhook_delivery", 2.0, _webhooks))

    # 3. Knowledge embedding (local ONNX model only; no paid embedding API).
    model_path = (os.environ.get("UCVE_EMBEDDING_MODEL_PATH") or "").strip()
    if not model_path:
        specs.append(
            JobSpec(
                "knowledge_embedding",
                5.0,
                None,
                disabled_reason="UCVE_EMBEDDING_MODEL_PATH not configured",
            )
        )
    else:
        from core.rag.embedders.local_onnx import LocalONNXEmbedder
        from core.rag.repository import PostgresKnowledgeVectorRepository
        from worker_jobs.kb_ingestion import KnowledgeEmbeddingWorker

        kb_worker = KnowledgeEmbeddingWorker(
            PostgresKnowledgeVectorRepository(database),
            LocalONNXEmbedder(model_path),
            runner_id,
        )

        async def _embed_once() -> bool:
            return await kb_worker.process_next() is not None

        async def _knowledge() -> int:
            return await drain(_embed_once, DRAIN_BATCH)

        specs.append(JobSpec("knowledge_embedding", 3.0, _knowledge))

    # 4. Retention and tenant erasure (object deletion, then database rows).
    from core.db.repos.privacy_repo import PostgresPrivacyJobRepository
    from core.storage.post_call_objects import get_default_post_call_object_store
    from worker_jobs.privacy_deletion import PrivacyDeletionWorker

    privacy_repository = PostgresPrivacyJobRepository(database)
    privacy_worker = PrivacyDeletionWorker(
        repository=privacy_repository,
        object_store=get_default_post_call_object_store(),
        worker_id=runner_id,
    )

    async def _privacy() -> int:
        return await drain(privacy_worker.run_once, DRAIN_BATCH)

    specs.append(JobSpec("privacy_deletion", 5.0, _privacy))

    # 5. Enqueue calls whose retention window has passed (singleton, idempotent).
    async def _retention_enqueue() -> int:
        return await privacy_repository.enqueue_due_retention(limit=500)

    specs.append(
        JobSpec("retention_enqueue", 900.0, _retention_enqueue, singleton=True)
    )

    # 6. Queue depth gauges and dead-letter alerts (singleton).
    async def _observe() -> int:
        return await observe_queues(database, alerts)

    specs.append(JobSpec("queue_observer", 60.0, _observe, singleton=True))
    return specs
