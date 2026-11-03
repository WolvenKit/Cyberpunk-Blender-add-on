import base64
import os
import tempfile

from ...assetio.atomic import atomic_replace_staged, atomic_write_bytes
from ...blender.physics.bridge_session import require_initialized_bridge
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)


def export_cooked_shape(shape, filepath):
    if not shape.cooked_data:
        raise ValueError("Mesh not cooked yet. Run 'Cook' first.")
    data = base64.b64decode(shape.cooked_data.encode("ascii"))
    atomic_write_bytes(filepath, data)
    return len(data)


def export_native_scene(filepath, context=None):
    target = os.path.abspath(os.fspath(filepath))
    directory = os.path.dirname(target) or os.curdir
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(target)}.", suffix=".tmp", dir=directory
    )
    os.close(descriptor)
    try:
        if not require_initialized_bridge(context).export_scene(temporary):
            raise RuntimeError("Export Failed")
        atomic_replace_staged({target: temporary})
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                debug_exception(
                    _LOG, "Could not remove the temporary file %s", temporary
                )
