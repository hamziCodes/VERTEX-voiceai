"""Post-Call Async Worker Job Processor — Orchestrates extraction, verification, review & dispatch."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from post_call.extraction.schema import TenantExtractionSchema
from post_call.extraction.service import ExtractionService
from post_call.models.call_record import CallRecord
from post_call.review.queue import HumanReviewQueue
from post_call.summarization.service import SummarizationService
from post_call.verification.service import VerificationService
from post_call.webhook.dispatcher import WebhookDispatcher
from post_call.webhook.targets import TenantWebhookTarget

logger = logging.getLogger(__name__)


class PostCallWorkerProcessor:
    """Async worker processing CallRecord items into extracted CRM payloads."""

    def __init__(
        self,
        extraction_service: ExtractionService | None = None,
        verification_service: VerificationService | None = None,
        review_queue: HumanReviewQueue | None = None,
        summarization_service: SummarizationService | None = None,
        webhook_dispatcher: WebhookDispatcher | None = None,
    ) -> None:
        self.extraction_service = extraction_service or ExtractionService()
        self.verification_service = verification_service or VerificationService()
        self.review_queue = review_queue or HumanReviewQueue()
        self.summarization_service = summarization_service or SummarizationService()
        self.webhook_dispatcher = webhook_dispatcher or WebhookDispatcher()

    async def process_record(
        self,
        record: CallRecord,
        schema: TenantExtractionSchema,
        target: TenantWebhookTarget | None = None,
    ) -> dict[str, Any]:
        """Process a CallRecord end-to-end:

        1. Extract fields via ExtractionService
        2. Verify fields & confidence via VerificationService
        3. Route low confidence fields to HumanReviewQueue
        4. Generate summary via SummarizationService
        5. Dispatch to webhook if target provided & review gate passes
        """
        transcript_text = " ".join(t.text for t in record.turns)
        extracted = await self.extraction_service.extract(
            transcript_text=transcript_text,
            schema=schema,
            compliance_tier=record.compliance_tier,
        )

        issues = self.verification_service.verify(extracted, schema)

        # Route issues / low-confidence to HumanReviewQueue
        for issue in issues:
            self.review_queue.enqueue(
                call_id=record.call_id,
                tenant_id=record.tenant_id,
                field_path=issue.field_name,
                extracted_value=extracted.get(issue.field_name),
                confidence=issue.confidence,
            )

        summary = self.summarization_service.summarize(record.turns)

        idempotency_key = f"dispatch-{record.call_id}"
        crm_payload = {
            "call_id": record.call_id,
            "tenant_id": record.tenant_id,
            "caller_id": record.caller_id,
            "extracted": extracted,
            "issues_count": len(issues),
            "summary": summary.executive_summary,
            "disposition": record.disposition.value,
            "idempotency_key": idempotency_key,
        }

        if target and len(issues) == 0:
            await self.webhook_dispatcher.dispatch(target, crm_payload, idempotency_key)

        return crm_payload
