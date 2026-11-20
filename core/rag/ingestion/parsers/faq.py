from __future__ import annotations

import json

from .base import IngestionParseError, ParsedDocument, ParsedSection


def parse_faq(content: bytes) -> ParsedDocument:
    try:
        items = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IngestionParseError("faq_malformed", "FAQ data is invalid.") from exc
    if not isinstance(items, list):
        raise IngestionParseError("faq_malformed", "FAQ data must be a list.")
    if len(items) > 1_000:
        raise IngestionParseError("faq_limit_exceeded", "FAQ exceeds the item limit.")
    sections: list[ParsedSection] = []
    for number, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise IngestionParseError("faq_item_invalid", "FAQ item is invalid.")
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question or not answer or len(question) > 2_000 or len(answer) > 20_000:
            raise IngestionParseError(
                "faq_item_invalid", "FAQ question or answer is invalid."
            )
        sections.append(
            ParsedSection(f"Q: {question}\nA: {answer}", {"faq_item": number})
        )
    return ParsedDocument(sections)
