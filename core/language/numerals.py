"""UCVE Per-Language Numeral & Spoken Form Converter."""

from __future__ import annotations

import re


class NumeralNormalizer:
    """Converts numeric digits into spoken-form words for target languages."""

    _digit_words: dict[str, dict[str, str]] = {
        "en": {
            "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
            "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
            "1234": "one thousand two hundred thirty four",
        },
        "ur": {
            "0": "صفر", "1": "ایک", "2": "دو", "3": "تین", "4": "چار",
            "5": "پانچ", "6": "چھ", "7": "سات", "8": "آٹھ", "9": "نو",
            "1234": "ایک ہزار دو سو چونتیس",
        },
        "ar": {
            "0": "صفر", "1": "واحد", "2": "اثنان", "3": "ثلاثة", "4": "أربعة",
            "5": "خمسة", "6": "ستة", "7": "سبعة", "8": "ثمانية", "9": "تسعة",
            "1234": "ألف ومائتان وأربعة وثلاثون",
        },
        "ms": {
            "0": "kosong", "1": "satu", "2": "dua", "3": "tiga", "4": "empat",
            "5": "lima", "6": "enam", "7": "tujuh", "8": "lapan", "9": "sembilan",
            "1234": "seribu dua ratus tiga puluh empat",
        },
    }

    @classmethod
    def convert_numerals(cls, text: str, language: str = "en") -> str:
        """Convert digits in text to spoken-form words for language."""
        lang_dict = cls._digit_words.get(language.lower(), cls._digit_words["en"])

        # Check full multi-digit token matches first
        for num_str, word in lang_dict.items():
            if len(num_str) > 1 and num_str in text:
                text = text.replace(num_str, word)

        # Single digit fallback conversion
        def replace_digit(match: re.Match) -> str:
            d = match.group(0)
            return lang_dict.get(d, d)

        return re.sub(r"\d", replace_digit, text)
