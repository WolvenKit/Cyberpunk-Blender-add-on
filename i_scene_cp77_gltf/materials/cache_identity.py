from __future__ import annotations


def filtered_material_data_identity(raw_material, parameters):
    if not isinstance(raw_material, dict):
        return raw_material
    data = raw_material.get("Data")
    if not isinstance(data, dict):
        return raw_material
    allowed = frozenset(str(parameter).casefold() for parameter in parameters)
    filtered = {
        key: value for key, value in data.items() if str(key).casefold() in allowed
    }
    if len(filtered) == len(data):
        return raw_material
    identity = dict(raw_material)
    identity["Data"] = filtered
    return identity
