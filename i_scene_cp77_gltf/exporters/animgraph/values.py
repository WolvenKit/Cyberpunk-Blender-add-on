from collections.abc import Iterable
from typing import Any

from ...assetio import animgraph_json
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)


def decode_optional(text: Any, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return animgraph_json.loads(str(text))
    except Exception:
        debug_exception(
            _LOG, "Could not decode the stored JSON value; using the default"
        )
        return default


def clone_json(value: Any) -> Any:
    return animgraph_json.loads(animgraph_json.dumps(value, indent=None))


def bools_as_ints(root: Any) -> Any:
    """WolvenKit writes and reads CBool as 0 or 1"""
    if root is True or root is False:
        return int(root)
    stack = [root]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                if value is True or value is False:
                    current[key] = int(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(current, list):
            for index, value in enumerate(current):
                if value is True or value is False:
                    current[index] = int(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
    return root


def vector4(values: Iterable[Any], *, default_w: float = 1.0) -> dict[str, Any]:
    vals = list(values)
    while len(vals) < 4:
        vals.append(default_w if len(vals) == 3 else 0.0)
    return {
        "$type": "Vector4",
        "X": float(vals[0]),
        "Y": float(vals[1]),
        "Z": float(vals[2]),
        "W": float(vals[3]),
    }
