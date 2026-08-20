"""UCVE Tenant Quota Limits Model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QuotaLimits:
    """Tenant quota limits and cap threshold configuration."""

    max_concurrent: int = 10
    max_minutes_month: int = 1000
    max_llm_tokens_month: int = 1000000
    rate_limit_per_min: int = 120
    soft_cap_percent: int = 80
    hard_cap_percent: int = 100
