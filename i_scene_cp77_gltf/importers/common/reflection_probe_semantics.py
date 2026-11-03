from __future__ import annotations

from ...assetio.values import coerce_float, unwrapped


def _field(data, key, default):
    """The field key of node data with its wrapper opened"""
    value = unwrapped(
        data.get(key, default) if isinstance(data, dict) else default,
        ("$value", "value"),
    )
    return default if value is None else value


def source_bool(data, key, default=False):
    value = _field(data, key, default)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes", "on", "1"}:
            return True
        if lowered in {"false", "no", "off", "0", ""}:
            return False
    return bool(value)


def source_float(data, key, default=0.0):
    return coerce_float(_field(data, key, default), default, unwrap=False, finite=False)


def scalar_edge_falloff(edge_scale):
    widths = []
    for value in edge_scale or ():
        try:
            strength = float(value)
        except (TypeError, ValueError):
            continue
        if strength <= 0.0:
            widths.append(1.0)
        else:
            widths.append(min(1.0, 1.0 / strength))
    return max(widths) if widths else 0.2
