"""E.164 Phone Number Verification & Normalization Helper."""

from __future__ import annotations


def normalize_phone_e164(phone_str: str | None, default_country_code: str = "1") -> str | None:
    """Normalize phone string into E.164 format (+1XXXXXXXXXX). Return None if invalid."""
    if not phone_str:
        return None
    cleaned = "".join(c for c in phone_str if c.isdigit() or c == "+")
    digits = "".join(c for c in cleaned if c.isdigit())
    if len(digits) == 10 and not cleaned.startswith("+"):
        return f"+{default_country_code}{digits}"
    if not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    if len(digits) < 10 or len(digits) > 15:
        return None
    return cleaned
