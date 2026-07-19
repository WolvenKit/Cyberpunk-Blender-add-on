"""Scalar parameter normalization for material handlers."""

from __future__ import annotations


def scalar_value(value, default=0.0, field_name=''):
    for _ in range(8):
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        if not isinstance(value, dict):
            return default

        keys = []
        if field_name:
            keys.append(field_name)
        keys.extend(('$value', 'Value', 'value'))
        for key in keys:
            if key in value and value[key] is not value:
                value = value[key]
                break
        else:
            payload_keys = [
                key for key in value
                if key not in {'$type', '$storage'}
                ]
            if len(payload_keys) == 1:
                value = value[payload_keys[0]]
                continue
            if 'X' in value:
                value = value['X']
                continue
            if 'x' in value:
                value = value['x']
                continue
            return default
    return default


def scalar_parameter_data(data, specs):
    normalized = dict(data)
    for key, _, _, _, default in specs:
        if key in data:
            normalized[key] = scalar_value(data[key], default, key)
    return normalized
