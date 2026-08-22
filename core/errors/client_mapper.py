"""Client Error Mapper — Converts internal errors into generic, caller-safe messages."""

from __future__ import annotations

from core.errors.codes import UCVEErrorCode
from core.errors.structured import StructuredError

GENERIC_CLIENT_MESSAGES: dict[UCVEErrorCode, str] = {
    UCVEErrorCode.AUTH_INVALID: "Authentication failed. Please check your credentials.",
    UCVEErrorCode.AUTH_EXPIRED: "Session expired. Please reconnect.",
    UCVEErrorCode.QUOTA_EXCEEDED: "Usage limit reached. Please contact support.",
    UCVEErrorCode.PROVIDER_TIMEOUT: "We're having trouble connecting right now. Please try again.",
    UCVEErrorCode.PROVIDER_UNAVAILABLE: "Service temporarily unavailable. Please try again shortly.",
    UCVEErrorCode.FSM_INVALID_TRANSITION: "An unexpected state occurred. Resetting call session.",
    UCVEErrorCode.HIPAA_BAA_REQUIRED: "Compliance policy configuration required.",
    UCVEErrorCode.TRUNK_UNAVAILABLE: "Telephony connection unavailable.",
    UCVEErrorCode.INTERNAL_ERROR: "An unexpected error occurred. Please try again.",
}


class ClientErrorMapper:
    """Sanitizes operational errors into caller-safe payloads for WebSocket clients."""

    @staticmethod
    def map_to_client_payload(error: StructuredError) -> dict[str, str]:
        """Return generic WebSocket error payload safe for public end-users.

        Removes stack traces, details, and internal IDs.
        """
        generic_msg = GENERIC_CLIENT_MESSAGES.get(error.code, "An error occurred. Please try again.")
        return {
            "type": "error",
            "code": error.code.value,
            "message": generic_msg,
        }
