from __future__ import annotations

CHINESE_COUNT_TOKEN = r"(?:[一二两三四五六七八九]?十[一二三四五六七八九]?|[一二两三四五六七八九])"

_CHINESE_DIGIT_VALUES = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def parse_chinese_count(token: str) -> int:
    if "十" not in token:
        return _CHINESE_DIGIT_VALUES[token]
    tens_text, ones_text = token.split("十", maxsplit=1)
    tens = _CHINESE_DIGIT_VALUES[tens_text] if tens_text else 1
    ones = _CHINESE_DIGIT_VALUES[ones_text] if ones_text else 0
    return (tens * 10) + ones
