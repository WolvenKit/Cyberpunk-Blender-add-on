from typing import Any


def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def get_idprop(obj: Any, key: str, default: Any = None) -> Any:
    try:
        return obj.get(key, default)
    except Exception:
        return default


def is_truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {'', '0', 'false', 'none', 'null'}
    return bool(value)
