"""UCVE Session Recording S3 Pointer Repository Layer."""

from __future__ import annotations

from core.db.models import SessionRecording


class RecordingRepository:
    """Repository managing audio recording S3 pointers and metadata."""

    def __init__(self) -> None:
        self._recordings: dict[str, SessionRecording] = {}

    async def save_recording(
        self, tenant_id: str, recording: SessionRecording
    ) -> SessionRecording:
        """Save recording pointer entity."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        if recording.tenant_id != tenant_id:
            raise PermissionError("Recording tenant_id mismatch with query context.")

        self._recordings[recording.session_id] = recording
        return recording

    async def get_recording(
        self, tenant_id: str, session_id: str
    ) -> SessionRecording | None:
        """Retrieve recording pointer by session ID scoped to tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        rec = self._recordings.get(session_id)
        if not rec:
            return None

        if rec.tenant_id != tenant_id:
            raise PermissionError(f"Cross-tenant access blocked for tenant '{tenant_id}'.")

        return rec
