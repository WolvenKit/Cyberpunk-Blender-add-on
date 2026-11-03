from typing import Any, Dict, Iterable

from ...assetio import animgraph_json as json_io
from ...redSpace.qs_transform import encode_wkit_quaternion


def decode_optional(text: Any, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json_io.loads(str(text))
    except Exception:
        return default


def clone_json(value: Any) -> Any:
    return json_io.loads(json_io.dumps(value, indent=None))


def cname(value: str) -> Dict[str, Any]:
    return {'$type': 'CName', '$storage': 'string', '$value': str(value or 'None')}


def vector4(values: Iterable[Any], *, default_w: float = 1.0) -> Dict[str, Any]:
    vals = list(values)
    while len(vals) < 4:
        vals.append(default_w if len(vals) == 3 else 0.0)
    return {
        '$type': 'Vector4',
        'X': float(vals[0]),
        'Y': float(vals[1]),
        'Z': float(vals[2]),
        'W': float(vals[3]),
    }


def quaternion(values: Iterable[Any]) -> Dict[str, Any]:
    return encode_wkit_quaternion(values, quaternion_order='xyzw')
