"""UCVE Session & Transcript Repository Layer."""

from __future__ import annotations

from core.db.models import Session, SessionTranscript


class SessionRepository:
    """Repository managing voice sessions and structured transcripts."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._transcripts: dict[str, SessionTranscript] = {}

    async def create_session(self, tenant_id: str, session: Session) -> Session:
        """Create new session entity."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        if session.tenant_id != tenant_id:
            raise PermissionError("Session tenant_id mismatch with query context.")

        self._sessions[session.id] = session
        return session

    async def get_session(self, tenant_id: str, session_id: str) -> Session | None:
        """Retrieve session by ID scoped to tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        session = self._sessions.get(session_id)
        if not session:
            return None

        if session.tenant_id != tenant_id:
            raise PermissionError(f"Cross-tenant access blocked for tenant '{tenant_id}'.")

        return session

    async def save_transcript(
        self, tenant_id: str, transcript: SessionTranscript
    ) -> SessionTranscript:
        """Persist structured transcript JSONB record (dual columns preferred)."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")
        if transcript.tenant_id != tenant_id:
            raise PermissionError("Transcript tenant_id mismatch with query context.")

        # Keep legacy `turns` mirrored from redacted when redacted present.
        if transcript.transcript_redacted and not transcript.turns:
            transcript.turns = list(transcript.transcript_redacted)
        self._transcripts[transcript.session_id] = transcript
        return transcript

    async def get_transcript(
        self, tenant_id: str, session_id: str
    ) -> SessionTranscript | None:
        """Retrieve transcript by session ID scoped to tenant."""
        if not tenant_id:
            raise PermissionError("Missing tenant_id in query context.")

        transcript = self._transcripts.get(session_id)
        if not transcript:
            return None

        if transcript.tenant_id != tenant_id:
            raise PermissionError(f"Cross-tenant access blocked for tenant '{tenant_id}'.")

        return transcript
