"""Phase 21: Structured Extraction & CRM Dispatch Contracts Test Suite."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from post_call.channels.whatsapp import WhatsAppDispatcher
from post_call.extraction.schema import ExtractionField, TenantExtractionSchema
from post_call.extraction.service import ExtractionService
from post_call.models.call_record import CallRecord
from post_call.models.diarized_turn import DiarizedTurn
from post_call.review.queue import HumanReviewQueue
from post_call.summarization.service import SummarizationService
from post_call.verification.datetime import parse_and_verify_datetime
from post_call.verification.phone import normalize_phone_e164
from post_call.verification.service import VerificationService
from post_call.webhook.dispatcher import WebhookDispatcher
from post_call.webhook.targets import TenantWebhookTarget
from post_call.worker import PostCallWorkerProcessor

REPO_ROOT = Path(__file__).resolve().parents[3]


class FixedExtractionProvider:
    provider_id = "test-extraction"
    model_id = "fixture-v1"

    def __init__(self, fields: dict[str, object]) -> None:
        self.fields = fields

    async def extract_json(self, **_: object) -> object:
        return {"fields": self.fields}


class FixedSummaryProvider:
    provider_id = "test-summary"
    model_id = "fixture-v1"

    async def summarize_json(self, **_: object) -> object:
        return {
            "executive_summary": "The caller provided their patient name.",
            "key_takeaways": ["Patient name provided"],
            "sentiment_trajectory": [],
            "evidence": [{"turn_id": 0, "quote": "patient_name John"}],
        }


def test_phase_plan_artifact_exists() -> None:
    plan = (
        REPO_ROOT
        / "voice_engine_plan"
        / "implementation_plan"
        / "phase_21_structured_extraction_and_crm_dispatch_contracts.md"
    )
    assert plan.is_file()


@pytest.mark.asyncio
async def test_extraction_returns_null_for_missing_fields() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[
            ExtractionField(name="patient_name", description="Patient name"),
            ExtractionField(name="insurance_id", description="Insurance ID"),
        ],
    )
    svc = ExtractionService(
        FixedExtractionProvider(
            {
                "patient_name": {
                    "value": "John Doe",
                    "confidence": 0.99,
                    "evidence": [{"turn_id": 0, "quote": "patient_name John Doe"}],
                }
            }
        )
    )
    turns = [
        DiarizedTurn(
            speaker="user",
            text="User called about patient_name John Doe",
            start_ms=0,
            end_ms=1000,
        )
    ]
    res = await svc.extract(turns, schema)
    assert res.fields["patient_name"].value == "John Doe"
    assert res.fields["patient_name"].source_turn_ids == (0,)
    assert res.fields["insurance_id"].value is None
    assert res.fields["insurance_id"].confidence == 0.0


def test_phone_and_date_normalization() -> None:
    assert normalize_phone_e164("(555) 019-9000") == "+15550199000"
    assert normalize_phone_e164("invalid") is None

    dt = parse_and_verify_datetime("2026-08-22T14:30:00Z")
    assert dt is not None
    assert dt.tzinfo is not None


def test_verification_enqueues_low_confidence_to_review_queue() -> None:
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[ExtractionField(name="appointment_date", type="datetime")],
    )
    v_svc = VerificationService()
    queue = HumanReviewQueue()

    extracted = {"appointment_date": "invalid_date_string"}
    conf_map = {"appointment_date": 0.5}  # Low confidence

    issues = v_svc.verify(
        extracted, schema, confidence_map=conf_map, min_confidence_threshold=0.75
    )
    assert len(issues) >= 1

    for issue in issues:
        queue.enqueue(
            call_id=uuid4(),
            tenant_id=schema.tenant_id,
            field_path=issue.field_name,
            extracted_value=extracted[issue.field_name],
            confidence=issue.confidence,
        )

    pending = queue.get_pending(schema.tenant_id)
    assert len(pending) == len(issues)


@pytest.mark.asyncio
async def test_webhook_hmac_and_fail_closed_without_secret() -> None:
    dispatcher = WebhookDispatcher()
    target = TenantWebhookTarget(
        tenant_id=uuid4(),
        url="https://api.clinic.com/webhook",
        secret="test-only-secret",
    )

    sig = dispatcher.compute_signature(b'{"key":"val"}', target.secret)
    assert len(sig) == 64  # SHA256 hex string

    # Fail closed without secret
    target_no_secret = TenantWebhookTarget(
        tenant_id=uuid4(),
        url="https://api.clinic.com/webhook",
        secret="",
    )
    with pytest.raises(ValueError) as exc_info:
        await dispatcher.dispatch(
            target_no_secret, {"payload": 1}, idempotency_key="key1"
        )
    assert "Webhook shared secret is missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_hipaa_blocks_extraction_without_baa_ack() -> None:
    svc_no_baa = ExtractionService(hipaa_baa_acknowledged=False)
    schema = TenantExtractionSchema(
        tenant_id=uuid4(), fields=[ExtractionField(name="ssn")]
    )
    with pytest.raises(PermissionError) as exc_info:
        await svc_no_baa.extract([], schema, compliance_tier="hipaa")
    assert "HIPAA tier requires signed BAA acknowledgment" in str(exc_info.value)


def test_schema_rejects_exceeding_max_fields() -> None:
    fields = [ExtractionField(name=f"f_{i}") for i in range(55)]
    schema = TenantExtractionSchema(tenant_id=uuid4(), fields=fields, max_fields=50)
    with pytest.raises(ValueError) as exc_info:
        schema.validate_schema()
    assert "exceeds max_fields" in str(exc_info.value)


def test_whatsapp_dispatcher_is_uninstantiable_abstract_stub() -> None:
    with pytest.raises(TypeError):
        WhatsAppDispatcher()  # type: ignore


@pytest.mark.asyncio
async def test_end_to_end_worker_processor() -> None:
    processor = PostCallWorkerProcessor(
        extraction_service=ExtractionService(
            FixedExtractionProvider(
                {
                    "patient_name": {
                        "value": "John",
                        "confidence": 0.99,
                        "evidence": [{"turn_id": 0, "quote": "patient_name John"}],
                    }
                }
            )
        ),
        summarization_service=SummarizationService(FixedSummaryProvider()),
    )
    schema = TenantExtractionSchema(
        tenant_id=uuid4(),
        fields=[ExtractionField(name="patient_name")],
    )

    record = CallRecord(
        tenant_id=schema.tenant_id,
        agent_id=uuid4(),
        session_id=uuid4(),
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        turns=[
            DiarizedTurn(
                speaker="user", text="patient_name John", start_ms=0, end_ms=1000
            )
        ],
    )

    target = TenantWebhookTarget(
        tenant_id=schema.tenant_id,
        url="https://clinic.com/webhook",
        secret="valid-secret-key",
    )

    result = await processor.process_record(record, schema, target)
    assert result["call_id"] == record.call_id
    assert result["summary"]["provider_id"] == "test-summary"
    assert result["dispatch_state"] == "blocked_for_phase_11c"
