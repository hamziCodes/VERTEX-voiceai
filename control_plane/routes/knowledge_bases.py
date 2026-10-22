"""Control Plane Knowledge Base API Router Stub."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from control_plane.auth.context import AuthContext
from control_plane.auth.dependencies import enforce_tenant_access, require_permission

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])
KnowledgeReader = Annotated[AuthContext, Depends(require_permission("knowledge:read"))]


@router.get("/status/{tenant_id}")
async def get_kb_status(
    tenant_id: UUID,
    auth: KnowledgeReader,
) -> dict[str, Any]:
    """Fetch knowledge base status and chunk counts for tenant."""
    enforce_tenant_access(auth, str(tenant_id))
    return {"tenant_id": tenant_id, "status": "ready", "total_chunks": 42}
