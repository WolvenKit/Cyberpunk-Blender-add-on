import json

from ..values import plain_value


def event_array(value, action_name="", error_type=ValueError) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            value = json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            raise error_type(
                f"Action {action_name!r} property 'animEvents' contains invalid JSON."
            ) from error
    if hasattr(value, "to_list"):
        value = value.to_list()
    plain = plain_value(value)
    if plain is None:
        return []
    if isinstance(plain, list):
        return plain
    if isinstance(plain, dict):
        if not plain:
            return []
        if "type" in plain or "eventName" in plain:
            return [plain]
        indexed = []
        for key, item in plain.items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                indexed = []
                break
            indexed.append((index, item))
        if indexed:
            indexed.sort(key=lambda pair: pair[0])
            return [item for _, item in indexed]
        values = list(plain.values())
        if values and all(isinstance(item, dict) for item in values):
            return values
    raise error_type(
        f"Action {action_name!r} property 'animEvents' could not be converted "
        f"from {type(value).__name__} to a JSON array."
    )
