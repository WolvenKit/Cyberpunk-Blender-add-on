import base64

from ...assetio.files import read_bytes
from .bridge_session import require_initialized_bridge


def decode_cooked_geometry(
    shape_type, cooked_data, context=None, heightfield_scale=None
):
    if not cooked_data:
        raise ValueError("Cooked geometry buffer is empty")
    if isinstance(cooked_data, str):
        raw = base64.b64decode(cooked_data.encode("ascii"))
    else:
        raw = bytes(cooked_data)
    bridge = require_initialized_bridge(context)
    scale = list(heightfield_scale or ())
    data = bridge.get_cooked_geometry(str(shape_type), raw, scale)
    if not isinstance(data, dict):
        raise TypeError(f"PhysX decoder returned {type(data).__name__}, expected dict")
    vertices = data.get("vertices") or ()
    indices = data.get("indices") or ()
    if len(vertices) < 3 or len(vertices) % 3:
        raise ValueError(f"Decoded {shape_type} geometry has invalid vertex data")
    if len(indices) < 3 or len(indices) % 3:
        raise ValueError(f"Decoded {shape_type} geometry has invalid triangle indices")
    vertex_count = len(vertices) // 3
    normalized_indices = [int(value) for value in indices]
    if min(normalized_indices) < 0 or max(normalized_indices) >= vertex_count:
        raise ValueError(f"Decoded {shape_type} geometry has out-of-range indices")
    return {
        "vertices": [float(value) for value in vertices],
        "indices": normalized_indices,
    }


def import_cooked_shape(shape, filepath):
    data = read_bytes(filepath)
    shape.cooked_data = base64.b64encode(data).decode("ascii")
    shape.is_cooked = True
    return len(data)


def import_native_scene(filepath, context=None):
    if not require_initialized_bridge(context).import_scene(filepath):
        raise RuntimeError("Import Failed")
