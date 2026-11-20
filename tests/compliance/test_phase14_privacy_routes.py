"""Phase 14: customer privacy routes — permissions, honesty and error paths."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from core.compliance.privacy_jobs import (
    PrivacyDeletionJob,
    PrivacyJobConflictError,
    PrivacyJobKind,
)
from core.db.models import Tenant


class FakePrivacyRepository:
    def __init__(self) -> None:
        self.calls: dict[UUID, bool] = {}
        self.jobs: dict[UUID, PrivacyDeletionJob] = {}

    def _job(
        self, tenant: UUID, kind: PrivacyJobKind, call: UUID | None
    ) -> PrivacyDeletionJob:
        now = datetime.now(UTC)
        job = PrivacyDeletionJob(
            job_id=uuid4(),
            tenant_id=tenant,
            kind=kind,
            request_key="k",
            call_id=call,
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.job_id] = job
        return job

    async def set_legal_hold(self, tenant, call, *, hold, actor):
        if call not in self.calls:
            return False
        self.calls[call] = hold
        return True

    async def request_call_deletion(self, tenant, call, *, actor):
        if call not in self.calls:
            return None
        if self.calls[call]:
            raise PrivacyJobConflictError("held")
        return self._job(tenant, PrivacyJobKind.RETENTION, call)

    async def request_tenant_erasure(self, tenant, *, actor):
        return self._job(tenant, PrivacyJobKind.TENANT_ERASURE, None)

    async def get_for_tenant(self, tenant, job_id):
        job = self.jobs.get(job_id)
        if job is None or job.tenant_id != tenant:
            raise KeyError(job_id)
        return job

    async def events(self, job_id):
        return [{"event": "requested"}]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UCVE_ENV", "test")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "test-mint-secret-value")
    monkeypatch.setenv("UCVE_JWT_SECRET", "test-jwt-secret-value-32-bytes-ok")
    from control_plane.app import app

    with TestClient(app) as test_client:
        yield test_client


def _headers(tenant: str, role: str, scopes: list[str]) -> dict[str, str]:
    from control_plane.app import app

    raw, _ = app.state.api_keys.generate_api_key(
        tenant, "privacy-test", scopes=scopes, role=role, subject_id="privacy-test"
    )
    return {"Authorization": f"Bearer {raw}", "X-Tenant-Id": tenant}


def test_without_durable_storage_privacy_operations_answer_503(
    client: TestClient,
) -> None:
    tenant = str(uuid4())
    headers = _headers(
        tenant, "compliance_admin", ["erasure:execute", "legal_hold:manage"]
    )
    response = client.post(f"/v1/conversations/{uuid4()}/deletion", headers=headers)
    assert response.status_code == 503
    assert "durable storage" in response.json()["detail"]


def test_routes_enforce_compliance_permissions(client: TestClient) -> None:
    from control_plane.app import app

    app.state.privacy_repository = FakePrivacyRepository()
    try:
        tenant = str(uuid4())
        viewer = _headers(tenant, "tenant_viewer", ["conversation:read"])
        for method, path, body in (
            (
                "post",
                f"/v1/conversations/{uuid4()}/legal-hold",
                {"hold": True, "reason": "litigation hold"},
            ),
            ("post", f"/v1/conversations/{uuid4()}/deletion", None),
            ("post", "/v1/workspace/erasure", {"confirm_workspace_name": "x"}),
            ("get", f"/v1/privacy-jobs/{uuid4()}", None),
        ):
            response = client.request(method.upper(), path, headers=viewer, json=body)
            assert response.status_code == 403, path
            assert client.request(method.upper(), path, json=body).status_code == 401
    finally:
        app.state.privacy_repository = None


def test_hold_deletion_and_erasure_flow(client: TestClient) -> None:
    import asyncio

    from control_plane.app import app

    repository = FakePrivacyRepository()
    app.state.privacy_repository = repository
    try:
        tenant = str(uuid4())
        asyncio.run(
            app.state.mint_ctx.tenant_repo.create_tenant(
                Tenant(id=tenant, name="Acme Clinic")
            )
        )
        headers = _headers(
            tenant, "compliance_admin", ["erasure:execute", "legal_hold:manage"]
        )
        call = uuid4()
        repository.calls[call] = False

        missing = client.post(
            f"/v1/conversations/{uuid4()}/legal-hold",
            headers=headers,
            json={"hold": True, "reason": "litigation hold"},
        )
        assert missing.status_code == 404
        short = client.post(
            f"/v1/conversations/{call}/legal-hold",
            headers=headers,
            json={"hold": True, "reason": "x"},
        )
        assert short.status_code == 422
        held = client.post(
            f"/v1/conversations/{call}/legal-hold",
            headers=headers,
            json={"hold": True, "reason": "litigation hold 2026-11"},
        )
        assert held.json() == {"call_id": str(call), "legal_hold": True}
        assert (
            client.post(
                f"/v1/conversations/{call}/deletion", headers=headers
            ).status_code
            == 409
        )

        client.post(
            f"/v1/conversations/{call}/legal-hold",
            headers=headers,
            json={"hold": False, "reason": "matter closed 2026-11"},
        )
        accepted = client.post(f"/v1/conversations/{call}/deletion", headers=headers)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]
        status = client.get(f"/v1/privacy-jobs/{job_id}", headers=headers).json()
        assert status["state"] == "queued" and status["events"] == [
            {"event": "requested"}
        ]

        other = _headers(str(uuid4()), "compliance_admin", ["erasure:execute"])
        assert (
            client.get(f"/v1/privacy-jobs/{job_id}", headers=other).status_code == 404
        )

        wrong = client.post(
            "/v1/workspace/erasure",
            headers=headers,
            json={"confirm_workspace_name": "Acme"},
        )
        assert wrong.status_code == 422
        erase = client.post(
            "/v1/workspace/erasure",
            headers=headers,
            json={"confirm_workspace_name": "Acme Clinic"},
        )
        assert erase.status_code == 202 and erase.json()["kind"] == "tenant_erasure"
    finally:
        app.state.privacy_repository = None
