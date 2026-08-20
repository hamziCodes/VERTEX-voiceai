"""UCVE GDPR Erasure Orchestrator."""

from __future__ import annotations

import datetime
from typing import Any, Protocol


class ErasureRepos(Protocol):
    async def delete_tenant(self, tenant_id: str) -> bool: ...


class ErasureOrchestrator:
    """Orchestrator processing GDPR right-to-be-forgotten erasure requests."""

    def __init__(self) -> None:
        self._erasure_log: list[dict[str, Any]] = []
        self._session_store: dict[str, dict[str, Any]] = {}

    def register_session_fixture(self, tenant_id: str, session_id: str) -> None:
        """Test/helper: track an in-memory session row for erasure proof."""
        self._session_store[session_id] = {"tenant_id": tenant_id, "session_id": session_id}

    def has_session(self, session_id: str) -> bool:
        return session_id in self._session_store

    def execute_tenant_erasure(
        self, tenant_id: str, s3_client: Any = None, repos: Any = None
    ) -> dict[str, Any]:
        """Cascade delete tenant artifacts. Never report completed on no-op."""
        if not tenant_id:
            raise ValueError("tenant_id is required for erasure execution.")

        deleted_db = False
        deleted_s3 = False
        cascaded: list[str] = []

        if repos is not None:
            delete_fn = getattr(repos, "delete_tenant", None)
            if delete_fn is None:
                return {
                    "tenant_id": tenant_id,
                    "status": "failed",
                    "reason": "repos missing delete_tenant",
                }
            import asyncio

            result = delete_fn(tenant_id)
            if asyncio.iscoroutine(result):
                deleted_db = asyncio.get_event_loop().run_until_complete(result)
            else:
                deleted_db = bool(result)
            if deleted_db:
                cascaded.extend(
                    ["sessions", "session_transcripts", "session_recordings", "tenant_credentials"]
                )
        else:
            # In-memory fixture path used by unit tests
            to_del = [sid for sid, row in self._session_store.items() if row["tenant_id"] == tenant_id]
            for sid in to_del:
                del self._session_store[sid]
            deleted_db = bool(to_del)
            if deleted_db:
                cascaded.append("sessions")

        if s3_client is not None:
            delete_prefix = getattr(s3_client, "delete_tenant_prefix", None) or getattr(
                s3_client, "delete_objects", None
            )
            if delete_prefix is None:
                return {
                    "tenant_id": tenant_id,
                    "status": "failed",
                    "reason": "s3_client missing delete API",
                    "cascaded_artifacts": cascaded,
                }
            try:
                delete_prefix(tenant_id)
                deleted_s3 = True
                cascaded.append("s3_objects")
            except Exception as exc:
                return {
                    "tenant_id": tenant_id,
                    "status": "failed",
                    "reason": f"s3 delete failed: {exc}",
                    "cascaded_artifacts": cascaded,
                }

        if repos is None and s3_client is None and not deleted_db:
            record = {
                "tenant_id": tenant_id,
                "status": "failed",
                "reason": "no-op erasure refused (no repos/s3/fixtures)",
            }
            self._erasure_log.append(record)
            return record

        if (repos is not None and not deleted_db) or (s3_client is not None and not deleted_s3 and "s3_objects" not in cascaded):
            record = {
                "tenant_id": tenant_id,
                "status": "failed",
                "reason": "incomplete cascade",
                "cascaded_artifacts": cascaded,
            }
            self._erasure_log.append(record)
            return record

        record = {
            "tenant_id": tenant_id,
            "status": "completed",
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "cascaded_artifacts": cascaded,
        }
        self._erasure_log.append(record)
        return record
