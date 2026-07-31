from typing import Any

from ....assetio.values import cname_text


def cname_value(value: Any, default: str = '') -> str:
    return cname_text(value, default)


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def int_number(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)
