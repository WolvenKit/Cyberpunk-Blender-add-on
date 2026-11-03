from typing import Any

<<<<<<< Updated upstream
=======
from ...assetio.values import coerce_float
from ...core.log import get_logger, log_once

_LOG = get_logger(__name__)

>>>>>>> Stashed changes

def get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
<<<<<<< Updated upstream
    except Exception:
=======
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("get_attr", type(error).__name__),
            "get attr: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return default


def get_idprop(obj: Any, key: str, default: Any = None) -> Any:
    try:
        return obj.get(key, default)
<<<<<<< Updated upstream
    except Exception:
=======
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("get_idprop", type(error).__name__),
            "get idprop: fell back after %s",
            error,
            exc_info=True,
        )
>>>>>>> Stashed changes
        return default


def is_truthy(value: Any) -> bool:
    if isinstance(value, str):
<<<<<<< Updated upstream
        return value.strip().lower() not in {'', '0', 'false', 'none', 'null'}
    return bool(value)
=======
        return value.strip().lower() not in {"", "0", "false", "none", "null"}
    return bool(value)


def node_property_map(node: Any) -> dict[str, Any]:
    return {
        str(getattr(item, "key", "") or getattr(item, "json_path", "") or ""): item
        for item in getattr(node, "red_properties", ()) or ()
    }


def indexed_node_property_map(node: Any) -> dict[str, tuple[int, Any]]:
    return {
        str(getattr(item, "key", "") or getattr(item, "json_path", "") or ""): (
            index,
            item,
        )
        for index, item in enumerate(getattr(node, "red_properties", ()) or ())
    }


def property_float(properties: dict[str, Any], key: str, default: float = 0.0) -> float:
    item = properties.get(key)
    value = getattr(item, "float_value", default) if item is not None else default
    return coerce_float(value, default, unwrap=False, finite=False)


def property_string(properties: dict[str, Any], key: str, default: str = "") -> str:
    item = properties.get(key)
    return (
        str(getattr(item, "string_value", default) or default)
        if item is not None
        else str(default)
    )


def property_bool(properties: dict[str, Any], key: str, default: bool = False) -> bool:
    item = properties.get(key)
    return (
        bool(getattr(item, "bool_value", default))
        if item is not None
        else bool(default)
    )


def property_vector(
    properties: dict[str, Any],
    key: str,
    default: tuple[float, ...],
) -> tuple[float, ...]:
    item = properties.get(key)
    if item is None:
        return tuple(float(value) for value in default)
    value = tuple(getattr(item, "vector_value", default) or default)
    return tuple(
        float(value[index]) if index < len(value) else float(fallback)
        for index, fallback in enumerate(default)
    )


def node_property_float(node: Any, key: str, default: float = 0.0) -> float:
    return property_float(node_property_map(node), key, default)


def node_property_string(node: Any, key: str, default: str = "") -> str:
    return property_string(node_property_map(node), key, default)


def clear_collection(collection: Any) -> None:
    try:
        collection.clear()
    except (AttributeError, ReferenceError, RuntimeError, TypeError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("clear_collection", type(error).__name__),
            "clear collection: fell back after %s",
            error,
            exc_info=True,
        )
        while len(collection):
            collection.remove(len(collection) - 1)


def move_item(collection: Any, index: int, delta: int) -> int:
    if not collection:
        return 0
    target = max(0, min(len(collection) - 1, index + delta))
    if target != index:
        collection.move(index, target)
    return target


def edit_collection(collection: Any, index: int, action: str, *, initialize=None):
    """Apply ADD, REMOVE, UP or DOWN to an editor collection and return its new active index"""
    if action == "ADD":
        item = collection.add()
        if initialize is not None:
            initialize(item)
        return len(collection) - 1
    if not collection:
        return None
    if action == "REMOVE":
        collection.remove(max(0, min(index, len(collection) - 1)))
        return min(index, max(0, len(collection) - 1))
    if action == "UP":
        return move_item(collection, index, -1)
    if action == "DOWN":
        return move_item(collection, index, 1)
    return None
>>>>>>> Stashed changes
