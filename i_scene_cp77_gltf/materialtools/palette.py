import ast
from pathlib import Path

from .constants import ENUM_NONE, OVERRIDE_ENUM_KEYS
from .state import normalize_depot_path, resolve_material_state

_ENUM_CACHE = {}
_PARSED_OVERRIDE_CACHE = {}


def clear_palette_caches():
    _ENUM_CACHE.clear()
    _PARSED_OVERRIDE_CACHE.clear()


def palette_enum_key(palette, key, values=()):
    try:
        palette_id = int(palette.as_pointer())
    except (AttributeError, ReferenceError, TypeError, ValueError):
        palette_id = id(palette)
    try:
        name = palette.name
    except (AttributeError, ReferenceError):
        name = ""
    return palette_id, name, str(key), tuple(values)


def palette_values(palette, key):
    if palette is None:
        return ()
    try:
        values = palette.get(key, ())
    except (AttributeError, ReferenceError, TypeError):
        return ()
    if values is None:
        return ()
    try:
        return tuple(values)
    except TypeError:
        return ()


def cached_palette_enum(context, key):
    palette = resolve_material_state(context).palette
    if palette is None:
        return [(ENUM_NONE, "Unavailable", "No active multilayer palette")]
    values = palette_values(palette, key)
    cache_key = palette_enum_key(palette, key, values)
    cached = _ENUM_CACHE.get(cache_key)
    if cached is not None:
        return cached
    items = [
        (ENUM_NONE, "Custom / Unmatched", f"No matching {key} override"),
        *((str(value), str(value), f"Select {value}") for value in values),
    ]
    if not values:
        items[0] = (ENUM_NONE, "Unavailable", f"No {key} overrides")
    _ENUM_CACHE[cache_key] = items
    return items


def parse_override_vector(value):
    if isinstance(value, (tuple, list)):
        return tuple(float(item) for item in value)
    key = str(value)
    cached = _PARSED_OVERRIDE_CACHE.get(key)
    if cached is not None:
        return cached
    parsed = ast.literal_eval(key)
    if not isinstance(parsed, (tuple, list)):
        parsed = (parsed,)
    result = tuple(float(item) for item in parsed)
    _PARSED_OVERRIDE_CACHE[key] = result
    return result


def coerce_override_for_socket(socket, value):
    parsed = parse_override_vector(value)
    current = getattr(socket, "default_value", None)
    try:
        target_len = len(current)
    except TypeError:
        return parsed[0] if parsed else 0.0
    if len(parsed) == target_len:
        return parsed
    if len(parsed) > target_len:
        return parsed[:target_len]
    try:
        baseline = tuple(float(item) for item in current)
    except (TypeError, ValueError):
        baseline = (0.0,) * target_len
    return parsed + baseline[len(parsed):]


def apply_override_vector(layer_node, socket_name, enum_value):
    if enum_value == ENUM_NONE or layer_node is None:
        return False
    socket = getattr(layer_node, "inputs", None)
    socket = socket.get(socket_name) if socket is not None else None
    if socket is None:
        return False
    socket.default_value = coerce_override_for_socket(socket, enum_value)
    return True


def find_matching_scalar(palette, key, target, tolerance):
    for value in palette_values(palette, key):
        try:
            if abs(float(value) - float(target)) < tolerance:
                return str(value)
        except (TypeError, ValueError):
            continue
    return None


def find_matching_vector(palette, key, target, tolerance):
    try:
        target_values = tuple(float(item) for item in target)
    except (TypeError, ValueError):
        return None
    for value in palette_values(palette, key):
        try:
            parsed = parse_override_vector(value)
        except (SyntaxError, ValueError, TypeError):
            continue
        if not parsed or len(parsed) > len(target_values):
            continue
        error = sum(
            abs(component - target_values[index])
            for index, component in enumerate(parsed)
        )
        if error < tolerance:
            return str(value)
    return None


def mltemplate_name_from_path(template_path):
    name = str(template_path or "").replace("/", "\\").rsplit("\\", 1)[-1]
    lower = name.lower()
    if lower.endswith(".mltemplate.json"):
        return name[:-16]
    if lower.endswith(".mltemplate"):
        return name[:-11]
    return Path(name).stem


def template_identity(value):
    return normalize_depot_path(value)


def override_enum_items(kind, context):
    return cached_palette_enum(context, OVERRIDE_ENUM_KEYS[kind])
