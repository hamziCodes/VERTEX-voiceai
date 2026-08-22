"""SIP Trunk Configuration Data Model — Multi-trunk failover & credential vault references."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import UUID, uuid4


class SIPTrunkProvider(str, Enum):
    """Supported telephony carrier & trunk providers."""

    TELNYX = "telnyx"
    TWILIO = "twilio"
    PLIVO = "plivo"
    BANDWIDTH = "bandwidth"
    GENERIC_PTA = "generic_pta"


class SIPTrunkRole(str, Enum):
    """Trunk operational role in tenant failover chain."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SANDBOX = "sandbox"


@dataclass
class SIPTrunkConfig:
    """Config item for a single SIP trunk connection."""

    provider: SIPTrunkProvider
    credentials_ref: str  # Vault key ID, e.g. "vault://tenant_id/telnyx_key"
    webhook_public_key: str = ""
    priority: int = 1  # 1 = Highest priority
    role: SIPTrunkRole = SIPTrunkRole.PRIMARY
    enabled: bool = True
    region: str = "us"
    trunk_id: UUID = field(default_factory=uuid4)

    def validate(self) -> bool:
        """Validate trunk config integrity. Single trunk config is valid."""
        if not self.credentials_ref:
            return False
        return self.enabled
