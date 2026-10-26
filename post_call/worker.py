"""Lease-owned worker for durable post-call intelligence jobs."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from post_call.extraction.schema import TenantExtractionSchema
from post_call.extraction.service import (
    ExtractionService,
    IntelligenceOutputError,
    IntelligenceProviderUnavailableError,
)
from post_call.jobs.models import PostCallIntelligenceResult
from post_call.models.call_record import CallRecord
from post_call.models.policy import PostCallPolicy
from post_call.review.policy import ReviewPolicy
from post_call.summarization.service import SummarizationService
from post_call.verification.service import VerificationService


class PostCallConfigurationError(ValueError):
    pass


class PostCallJobWorker:
    """Claim one job, validate provider output, and atomically store its outcome."""

    def __init__(
        self,
        *,
        call_repository: Any,
        job_repository: Any,
        extraction_service: ExtractionService,
        summarization_service: SummarizationService,
        worker_id: str,
        review_policy: ReviewPolicy | None = None,
        verification_service: VerificationService | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required.")
        self.call_repository = call_repository
        self.job_repository = job_repository
        self.extraction_service = extraction_service
        self.summarization_service = summarization_service
        self.worker_id = worker_id
        self.review_policy = review_policy or ReviewPolicy()
        self.verification_service = verification_service or VerificationService()

    @staticmethod
    def _schema(job: Any) -> TenantExtractionSchema | None:
        raw = job.payload.get("extraction_schema")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise PostCallConfigurationError("Extraction schema must be an object.")
        allowed = {
            key: raw[key] for key in ("name", "fields", "max_fields") if key in raw
        }
        try:
            return TenantExtractionSchema(tenant_id=job.tenant_id, **allowed)
        except ValidationError as exc:
            raise PostCallConfigurationError(
                "Extraction schema snapshot is invalid."
            ) from exc

    async def run_once(self) -> bool:
        job = await self.job_repository.claim_next(self.worker_id)
        if job is None:
            return False
        try:
            call = await self.call_repository.get_call_by_id(job.tenant_id, job.call_id)
            policy = PostCallPolicy.model_validate(call.policy_snapshot)
            schema = self._schema(job)
            extraction = None
            issue_codes: tuple[str, ...] = ()
            provider_snapshot: dict[str, str] = {}
            if schema is not None:
                extraction = await self.extraction_service.extract(
                    call.turns, schema, call.compliance_tier
                )
                provider_snapshot["extraction_provider"] = extraction.provider_id
                provider_snapshot["extraction_model"] = extraction.model_id
                raw_values = {
                    name: field.value for name, field in extraction.fields.items()
                }
                confidences = {
                    name: field.confidence for name, field in extraction.fields.items()
                }
                issues = self.verification_service.verify(
                    raw_values, schema, confidence_map=confidences
                )
                issue_codes = tuple(
                    sorted(f"{issue.error_type}:{issue.field_name}" for issue in issues)
                )
            review_reasons = self.review_policy.reasons(
                policy=policy,
                schema=schema,
                extraction=extraction,
                verification_issue_codes=issue_codes,
                external_action_configured=bool(
                    job.payload.get("external_action_configured", False)
                ),
            )
            summary = await self.summarization_service.summarize(call.turns)
            if summary is not None:
                provider_snapshot["summary_provider"] = summary.provider_id
                provider_snapshot["summary_model"] = summary.model_id
            result = PostCallIntelligenceResult(
                tenant_id=job.tenant_id,
                call_id=job.call_id,
                extraction=(
                    extraction.model_dump(mode="json")
                    if extraction is not None
                    else None
                ),
                summary=(
                    summary.model_dump(mode="json") if summary is not None else None
                ),
                verification_issue_codes=issue_codes,
                provider_snapshot=provider_snapshot,
            )
            await self.job_repository.complete_job(
                job.job_id,
                worker_id=self.worker_id,
                result=result,
                review_reasons=review_reasons,
            )
            return True
        except PostCallConfigurationError:
            await self.job_repository.fail_job(
                job.job_id,
                worker_id=self.worker_id,
                error_code="configuration_invalid",
                safe_message="Post-call intelligence configuration is invalid.",
                retryable=False,
            )
            return True
        except PermissionError:
            await self.job_repository.fail_job(
                job.job_id,
                worker_id=self.worker_id,
                error_code="compliance_blocked",
                safe_message="Post-call intelligence is blocked by compliance policy.",
                retryable=False,
            )
            return True
        except IntelligenceProviderUnavailableError:
            await self.job_repository.fail_job(
                job.job_id,
                worker_id=self.worker_id,
                error_code="provider_unavailable",
                safe_message="Post-call intelligence provider is unavailable.",
                retryable=False,
            )
            return True
        except IntelligenceOutputError:
            await self.job_repository.fail_job(
                job.job_id,
                worker_id=self.worker_id,
                error_code="provider_output_invalid",
                safe_message="Post-call provider returned invalid structured output.",
                retryable=True,
            )
            return True
        except Exception:
            await self.job_repository.fail_job(
                job.job_id,
                worker_id=self.worker_id,
                error_code="processing_failed",
                safe_message="Post-call intelligence processing failed.",
                retryable=True,
            )
            return True


class PostCallWorkerProcessor:
    """Compatibility facade that validates intelligence without dispatching it."""

    def __init__(
        self,
        extraction_service: ExtractionService | None = None,
        verification_service: VerificationService | None = None,
        review_queue: Any | None = None,
        summarization_service: SummarizationService | None = None,
        webhook_dispatcher: Any | None = None,
    ) -> None:
        del review_queue, webhook_dispatcher
        self.extraction_service = extraction_service or ExtractionService()
        self.verification_service = verification_service or VerificationService()
        self.summarization_service = summarization_service or SummarizationService()

    async def process_record(
        self,
        record: CallRecord,
        schema: TenantExtractionSchema,
        target: Any | None = None,
    ) -> dict[str, Any]:
        extraction = await self.extraction_service.extract(
            record.turns, schema, record.compliance_tier
        )
        summary = await self.summarization_service.summarize(record.turns)
        issues = self.verification_service.verify(
            {name: value.value for name, value in extraction.fields.items()},
            schema,
            confidence_map={
                name: value.confidence for name, value in extraction.fields.items()
            },
        )
        return {
            "call_id": record.call_id,
            "tenant_id": record.tenant_id,
            "extracted": extraction.model_dump(mode="json"),
            "issues_count": len(issues),
            "summary": (
                summary.model_dump(mode="json") if summary is not None else None
            ),
            "dispatch_state": "blocked_for_phase_11c" if target is not None else "none",
        }
