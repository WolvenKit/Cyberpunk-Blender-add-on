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


def component_value(value, component, default=0.0):
    if isinstance(value, dict):
        for key in (component, component.lower()):
            if key in value:
                return scalar_value(value[key], default, component)

        axis_keys = {'X', 'Y', 'Z', 'W', 'x', 'y', 'z', 'w'}
        if any(key in value for key in axis_keys):
            return default

        for key in ('$value', 'Value', 'value'):
            nested = value.get(key)
            if nested is not None and nested is not value:
                return component_value(nested, component, default)

        payload_keys = [
            key for key in value
            if key not in {'$type', '$storage'}
            ]
        if len(payload_keys) == 1:
            nested = value[payload_keys[0]]
            if nested is not value:
                return component_value(nested, component, default)
        return default

    return scalar_value(value, default, component)


def scalar_parameter_data(data, specs):
    normalized = dict(data)
    for key, _, _, _, default in specs:
        if key in data:
            normalized[key] = scalar_value(data[key], default, key)
    return normalized
