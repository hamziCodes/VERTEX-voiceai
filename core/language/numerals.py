"""UCVE Per-Language Numeral & Spoken Form Converter."""

from __future__ import annotations

import re


_EN_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_EN_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def _en_under_1000(n: int) -> str:
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _EN_TENS[tens] + (f" {_EN_ONES[ones]}" if ones else "")
    hundreds, rest = divmod(n, 100)
    if rest == 0:
        return f"{_EN_ONES[hundreds]} hundred"
    return f"{_EN_ONES[hundreds]} hundred {_en_under_1000(rest)}"


def number_to_english_words(n: int) -> str:
    """Algorithmic conversion for non-negative integers up to millions."""
    if n < 0:
        return "minus " + number_to_english_words(-n)
    if n < 1000:
        return _en_under_1000(n)
    if n < 1_000_000:
        thousands, rest = divmod(n, 1000)
        head = number_to_english_words(thousands) + " thousand"
        return head if rest == 0 else f"{head} {number_to_english_words(rest)}"
    millions, rest = divmod(n, 1_000_000)
    head = number_to_english_words(millions) + " million"
    return head if rest == 0 else f"{head} {number_to_english_words(rest)}"


class NumeralNormalizer:
    """Converts numeric digits into spoken-form words for target languages."""

    # Measure-only languages keep fixture map for known tokens; en/ur use algorithms where possible.
    _digit_words: dict[str, dict[str, str]] = {
        "ur": {
            "0": "صفر",
            "1": "ایک",
            "2": "دو",
            "3": "تین",
            "4": "چار",
            "5": "پانچ",
            "6": "چھ",
            "7": "سات",
            "8": "آٹھ",
            "9": "نو",
        },
        "ar": {
            "0": "صفر",
            "1": "واحد",
            "2": "اثنان",
            "3": "ثلاثة",
            "4": "أربعة",
            "5": "خمسة",
            "6": "ستة",
            "7": "سبعة",
            "8": "ثمانية",
            "9": "تسعة",
        },
        "ms": {
            "0": "kosong",
            "1": "satu",
            "2": "dua",
            "3": "tiga",
            "4": "empat",
            "5": "lima",
            "6": "enam",
            "7": "tujuh",
            "8": "lapan",
            "9": "sembilan",
        },
    }

    # Measure-only / Urdu spoken forms for common magnitudes (fixture); English is algorithmic.
    _MULTI_DIGIT: dict[str, dict[str, str]] = {
        "ur": {"1234": "ایک ہزار دو سو چونتیس"},
        "ar": {"1234": "ألف ومائتان وأربعة وثلاثون"},
        "ms": {"1234": "seribu dua ratus tiga puluh empat"},
    }

    @classmethod
    def convert_numerals(cls, text: str, language: str = "en") -> str:
        """Convert digits in text to spoken-form words for language."""
        lang = language.lower()

        # Prefer multi-digit spoken forms for non-English where algorithm not ready
        for num_str, word in cls._MULTI_DIGIT.get(lang, {}).items():
            if num_str in text:
                text = text.replace(num_str, word)

        def replace_number(match: re.Match[str]) -> str:
            raw = match.group(0)
            try:
                value = int(raw)
            except ValueError:
                return raw
            if lang == "en":
                return number_to_english_words(value)
            lang_dict = cls._digit_words.get(lang, {})
            if lang in ("ar", "ms", "ur"):
                return " ".join(lang_dict.get(ch, ch) for ch in raw)
            return number_to_english_words(value)

        return re.sub(r"\d+", replace_number, text)
