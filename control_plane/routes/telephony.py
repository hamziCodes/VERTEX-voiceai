"""Control Plane Telephony Router — Telnyx webhooks & DID routing endpoints."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/telephony", tags=["telephony"])
