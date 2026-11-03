<<<<<<< Updated upstream
from typing import Any, Dict, Iterable

from ...assetio import animgraph_json as json_io
from ...redSpace.qs_transform import encode_wkit_quaternion
=======
from collections.abc import Iterable
from typing import Any

from ...assetio import animgraph_json
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)
>>>>>>> Stashed changes


def decode_optional(text: Any, default: Any = None) -> Any:
    if not text:
        return default
    try:
<<<<<<< Updated upstream
        return json_io.loads(str(text))
    except Exception:
=======
        return animgraph_json.loads(str(text))
    except Exception:
        debug_exception(
            _LOG, "Could not decode the stored JSON value; using the default"
        )
>>>>>>> Stashed changes
        return default


def clone_json(value: Any) -> Any:
<<<<<<< Updated upstream
    return json_io.loads(json_io.dumps(value, indent=None))


def cname(value: str) -> Dict[str, Any]:
    return {'$type': 'CName', '$storage': 'string', '$value': str(value or 'None')}


def vector4(values: Iterable[Any], *, default_w: float = 1.0) -> Dict[str, Any]:
=======
    return animgraph_json.loads(animgraph_json.dumps(value, indent=None))


def vector4(values: Iterable[Any], *, default_w: float = 1.0) -> dict[str, Any]:
>>>>>>> Stashed changes
    vals = list(values)
    while len(vals) < 4:
        vals.append(default_w if len(vals) == 3 else 0.0)
    return {
<<<<<<< Updated upstream
        '$type': 'Vector4',
        'X': float(vals[0]),
        'Y': float(vals[1]),
        'Z': float(vals[2]),
        'W': float(vals[3]),
    }


def quaternion(values: Iterable[Any]) -> Dict[str, Any]:
    return encode_wkit_quaternion(values, quaternion_order='xyzw')
=======
        "$type": "Vector4",
        "X": float(vals[0]),
        "Y": float(vals[1]),
        "Z": float(vals[2]),
        "W": float(vals[3]),
    }
>>>>>>> Stashed changes
