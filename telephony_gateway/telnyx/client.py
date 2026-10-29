"""Bounded Telnyx Dial client for controlled single-call outbound use."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from telephony_gateway.outbound import OutboundCallError


@dataclass(frozen=True, slots=True)
class TelnyxDialRequest:
    to: str
    from_number: str
    connection_id: str
    command_id: str
    stream_url: str
    time_limit_seconds: int
    tenant_id: UUID | None = None
    credential_ref: str | None = None


@dataclass(frozen=True, slots=True)
class TelnyxDialResult:
    call_control_id: str
    call_leg_id: str
    call_session_id: str


class TelnyxCallClient:
    """Issue one Dial command without leaking credentials or response bodies."""

    def __init__(
        self,
        *,
        api_key: str,
        http_client: httpx.AsyncClient,
        max_attempts: int = 2,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Telnyx API credential is required")
        if max_attempts < 1 or max_attempts > 3:
            raise ValueError("Telnyx dial attempts must be between one and three")
        self._api_key = api_key.strip()
        self._http = http_client
        self._max_attempts = max_attempts

    @staticmethod
    def _payload(request: TelnyxDialRequest) -> dict[str, Any]:
        return {
            "to": request.to,
            "from": request.from_number,
            "connection_id": request.connection_id,
            "command_id": request.command_id,
            "time_limit_secs": request.time_limit_seconds,
            "stream_url": request.stream_url,
            "stream_track": "inbound_track",
            "stream_codec": "PCMU",
            "stream_bidirectional_mode": "rtp",
            "stream_bidirectional_codec": "PCMU",
            "stream_bidirectional_sampling_rate": 8000,
            "stream_bidirectional_target_legs": "self",
            "stream_establish_before_call_originate": True,
            "send_silence_when_idle": True,
        }

    async def dial(self, request: TelnyxDialRequest) -> TelnyxDialResult:
        payload = self._payload(request)
        for attempt in range(1, self._max_attempts + 1):
            try:
                response = await self._http.post(
                    "/v2/calls",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=httpx.Timeout(2.0, connect=0.5, read=0.5, write=0.5),
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                if attempt < self._max_attempts:
                    continue
                raise OutboundCallError("carrier_unavailable") from exc
            except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                raise OutboundCallError(
                    "carrier_result_ambiguous", ambiguous=True
                ) from exc
            except httpx.HTTPError as exc:
                raise OutboundCallError("carrier_request_failed") from exc

            if 500 <= response.status_code <= 599:
                if attempt < self._max_attempts:
                    continue
                raise OutboundCallError("carrier_unavailable")
            if response.status_code == 429:
                raise OutboundCallError("carrier_rate_limited")
            if response.status_code < 200 or response.status_code >= 300:
                raise OutboundCallError("carrier_request_rejected")
            try:
                data = response.json()["data"]
                return TelnyxDialResult(
                    call_control_id=str(data["call_control_id"]),
                    call_leg_id=str(data["call_leg_id"]),
                    call_session_id=str(data["call_session_id"]),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise OutboundCallError(
                    "invalid_carrier_response", ambiguous=True
                ) from exc
        raise OutboundCallError("carrier_unavailable")


class CredentialResolvingTelnyxDialer:
    """Resolve one tenant BYOK secret only after the explicit live-call gate."""

    def __init__(self, *, vault: Any, http_client: httpx.AsyncClient) -> None:
        self._vault = vault
        self._http = http_client

    def __repr__(self) -> str:
        return "CredentialResolvingTelnyxDialer(gated=True)"

    async def dial(self, request: TelnyxDialRequest) -> TelnyxDialResult:
        if os.environ.get("RUN_LIVE_TELEPHONY") != "1":
            raise OutboundCallError("live_telephony_disabled")
        if request.tenant_id is None or not (request.credential_ref or "").strip():
            raise OutboundCallError("outbound_setup_not_ready")

        from core.secrets.exceptions import (
            DecryptionError,
            KMSBackendError,
            SecretNotFoundError,
        )
        from core.secrets.policy import CredentialTier

        try:
            credential = await self._vault.aresolve_credential(
                str(request.tenant_id),
                "telnyx",
                credential_ref=request.credential_ref,
                credential_type="api_key",
                tier=CredentialTier.BYOK,
            )
        except (DecryptionError, KMSBackendError, SecretNotFoundError) as exc:
            raise OutboundCallError("outbound_setup_not_ready") from exc
        client = TelnyxCallClient(api_key=credential.secret, http_client=self._http)
        return await client.dial(request)
