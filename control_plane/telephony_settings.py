"""Safe telephony policy persistence without carrier-side actions."""

from __future__ import annotations

import re
from datetime import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.db.async_pg import AsyncDatabase, get_default_database

_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


class TelephonyPolicySettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbound_enabled: bool = False
    allowed_destinations: tuple[str, ...] = ()
    calling_timezone: str = Field(default="UTC", min_length=1, max_length=64)
    window_start: time = time(9, 0)
    window_end: time = time(17, 0)
    max_concurrent_calls: int = Field(default=1, ge=1, le=1000)
    max_calls_per_minute: int = Field(default=1, ge=1, le=10_000)
    daily_spend_cap_cents: int = Field(default=100, ge=1, le=100_000_000)
    reserved_spend_cents_per_call: int = Field(default=1, ge=1)
    max_call_duration_seconds: int = Field(default=600, ge=1, le=14_400)

    @model_validator(mode="after")
    def validate_policy(self) -> TelephonyPolicySettings:
        if any(_E164.fullmatch(value) is None for value in self.allowed_destinations):
            raise ValueError("allowed destinations must use E.164 format")
        if self.outbound_enabled and not self.allowed_destinations:
            raise ValueError("enabled outbound calling requires an allowlist")
        if self.reserved_spend_cents_per_call > self.daily_spend_cap_cents:
            raise ValueError("per-call reserve cannot exceed daily cap")
        return self


class InMemoryTelephonySettingsRepository:
    def __init__(self) -> None:
        self._policies: dict[UUID, TelephonyPolicySettings] = {}

    async def get(self, tenant_id: UUID) -> dict[str, Any]:
        return {
            "policy": self._policies.get(tenant_id, TelephonyPolicySettings()),
            "trunk_configured": False,
            "telephony_entitled": False,
        }

    async def save(
        self, tenant_id: UUID, policy: TelephonyPolicySettings
    ) -> dict[str, Any]:
        self._policies[tenant_id] = policy
        return await self.get(tenant_id)


class PostgresTelephonySettingsRepository:
    def __init__(self, database: AsyncDatabase | Any | None = None) -> None:
        self.database = database or get_default_database()

    async def get(self, tenant_id: UUID) -> dict[str, Any]:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            cursor = await connection.execute(
                "SELECT enabled, allowed_destinations, calling_timezone, "
                "window_start, window_end, max_concurrent_calls, "
                "max_calls_per_minute, daily_spend_cap_cents, "
                "reserved_spend_cents_per_call, max_call_duration_seconds "
                "FROM telephony_outbound_policies WHERE tenant_id = %s",
                (tenant_id,),
            )
            row = await cursor.fetchone()
            trunk_cursor = await connection.execute(
                "SELECT EXISTS (SELECT 1 FROM sip_trunks WHERE tenant_id = %s "
                "AND provider = 'telnyx' AND enabled = TRUE "
                "AND credentials_ref <> '' AND connection_id <> '')",
                (tenant_id,),
            )
            trunk_row = await trunk_cursor.fetchone()
            entitlement_cursor = await connection.execute(
                "SELECT telephony_enabled FROM tenant_entitlements "
                "WHERE tenant_id = %s",
                (tenant_id,),
            )
            entitlement_row = await entitlement_cursor.fetchone()
        policy = TelephonyPolicySettings()
        if row is not None:
            policy = TelephonyPolicySettings(
                outbound_enabled=row[0],
                allowed_destinations=tuple(row[1]),
                calling_timezone=row[2],
                window_start=row[3],
                window_end=row[4],
                max_concurrent_calls=row[5],
                max_calls_per_minute=row[6],
                daily_spend_cap_cents=row[7],
                reserved_spend_cents_per_call=row[8],
                max_call_duration_seconds=row[9],
            )
        return {
            "policy": policy,
            "trunk_configured": bool(trunk_row and trunk_row[0]),
            "telephony_entitled": bool(entitlement_row and entitlement_row[0]),
        }

    async def save(
        self, tenant_id: UUID, policy: TelephonyPolicySettings
    ) -> dict[str, Any]:
        async with self.database.tenant_transaction(str(tenant_id)) as connection:
            if not policy.outbound_enabled and not policy.allowed_destinations:
                await connection.execute(
                    "DELETE FROM telephony_outbound_policies WHERE tenant_id = %s",
                    (tenant_id,),
                )
            else:
                await connection.execute(
                    "INSERT INTO telephony_outbound_policies "
                    "(tenant_id, enabled, allowed_destinations, calling_timezone, "
                    "window_start, window_end, max_concurrent_calls, "
                    "max_calls_per_minute, daily_spend_cap_cents, "
                    "reserved_spend_cents_per_call, max_call_duration_seconds) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (tenant_id) DO UPDATE SET enabled = EXCLUDED.enabled, "
                    "allowed_destinations = EXCLUDED.allowed_destinations, "
                    "calling_timezone = EXCLUDED.calling_timezone, "
                    "window_start = EXCLUDED.window_start, "
                    "window_end = EXCLUDED.window_end, "
                    "max_concurrent_calls = EXCLUDED.max_concurrent_calls, "
                    "max_calls_per_minute = EXCLUDED.max_calls_per_minute, "
                    "daily_spend_cap_cents = EXCLUDED.daily_spend_cap_cents, "
                    "reserved_spend_cents_per_call = "
                    "EXCLUDED.reserved_spend_cents_per_call, "
                    "max_call_duration_seconds = EXCLUDED.max_call_duration_seconds, "
                    "updated_at = NOW()",
                    (
                        tenant_id,
                        policy.outbound_enabled,
                        list(policy.allowed_destinations),
                        policy.calling_timezone,
                        policy.window_start,
                        policy.window_end,
                        policy.max_concurrent_calls,
                        policy.max_calls_per_minute,
                        policy.daily_spend_cap_cents,
                        policy.reserved_spend_cents_per_call,
                        policy.max_call_duration_seconds,
                    ),
                )
        return await self.get(tenant_id)
