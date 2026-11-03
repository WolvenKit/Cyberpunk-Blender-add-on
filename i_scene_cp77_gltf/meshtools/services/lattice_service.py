import math
<<<<<<< Updated upstream
=======
import os
import tempfile

>>>>>>> Stashed changes
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

<<<<<<< Updated upstream
MAGIC = b"LATZ"
VERSION = 3
INTERP_VALID = {"KEY_LINEAR", "KEY_CARDINAL", "KEY_BSPLINE", "KEY_CATMULL_ROM"}


# Helpers

=======
from ...assetio.atomic import atomic_replace_staged
from ...assetio.files import binary_reader
from ...blender.operator_results import require_finished
from ...core.log import debug_exception, get_logger

_LOG = get_logger(__name__)

MAGIC = b"LATZ"
VERSION = 3


>>>>>>> Stashed changes
def _bstr(s, n, enc="utf8"):
    if isinstance(s, (bytes, bytearray, np.bytes_)):
        b = bytes(s)
    else:
        b = str(s or "").encode(enc, "ignore")
    return np.array([b[:n].ljust(n, b"\x00")], dtype=f"|S{n}")


def _decode_bytes(val):
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf8", "ignore").rstrip("\x00")
    return val


def _points_to_np(lt, attr: str) -> np.ndarray:
    n = len(lt.points)
    buf = np.empty(n * 3, dtype=np.float32)
    lt.points.foreach_get(attr, buf)
    return buf.reshape(n, 3)


def _apply_points(lt, pts_f32: np.ndarray, attr: str):
    flat = np.asarray(pts_f32, dtype=np.float32, order="C").reshape(-1)
    lt.points.foreach_set(attr, flat)
    lt.update_tag()


def _normalize_quaternion(q):
    q = q.normalized()
<<<<<<< Updated upstream
    if q.w < 0.0: q.negate()
    return q


# Export

=======
    if q.w < 0.0:
        q.negate()
    return q


>>>>>>> Stashed changes
def save_lattice_npz(obj, filepath, *, compressed: bool = True):
    if obj is None or obj.type != "LATTICE":
        raise TypeError("save_lattice_npz: obj must be a LATTICE object")

    lt = obj.data
    U, V, W = int(lt.points_u), int(lt.points_v), int(lt.points_w)

<<<<<<< Updated upstream
    # Read rest and deform points from the lattice
    pts_co = _points_to_np(lt, "co")
    pts_codeform = _points_to_np(lt, "co_deform")

    # Decompose world transform
=======
    pts_co = _points_to_np(lt, "co")
    pts_codeform = _points_to_np(lt, "co_deform")

>>>>>>> Stashed changes
    loc_v, rot_q, scl_v = obj.matrix_world.decompose()
    q = _normalize_quaternion(rot_q)
    loc = np.array(loc_v[:], dtype=np.float32)
    quat = np.array([q.w, q.x, q.y, q.z], dtype=np.float32)
    scl = np.array(scl_v[:], dtype=np.float32)

<<<<<<< Updated upstream
    # Other metadata
=======
>>>>>>> Stashed changes
    iu = lt.interpolation_type_u
    iv = lt.interpolation_type_v
    iw = lt.interpolation_type_w

    arrays = dict(
<<<<<<< Updated upstream
            magic=_bstr(MAGIC, 4), version=np.array([VERSION], dtype=np.uint16),
            name=_bstr(obj.name, 64),
            U=np.array([U], dtype=np.uint16), V=np.array([V], dtype=np.uint16), W=np.array([W], dtype=np.uint16),
            interp=np.array([iu, iv, iw], dtype="|S16"),
            location=loc, rotation_quat=quat, scale=scl,
            use_outside=np.array([int(lt.use_outside)], dtype=np.uint8),
            points_rest=pts_co,
            points_deform=pts_codeform,
            )
    (np.savez_compressed if compressed else np.savez)(filepath, **arrays)
    return filepath


# Import

def load_lattice_npz(filepath, *, name=None, link_to_collection=None, update_view: bool = True):
    data = np.load(filepath, allow_pickle=False)

    # Helper function for reading the .npz file
    def _get1(key, cast=None, default=None):
        if key not in data.files: return default
        arr = data[key]
        val = arr.item() if arr.shape == () else (arr[0] if arr.ndim == 1 and arr.size == 1 else arr)
        val = _decode_bytes(val)
        return cast(val) if (cast and val is not None) else val

    # Load the file and read it

    if _get1("magic") != MAGIC.decode(): raise ValueError("Not a LATZ lattice file")
    U, V, W = int(_get1("U", int)), int(_get1("V", int)), int(_get1("W", int))
    pts_deform = np.array(data["points_deform"], dtype=np.float32)
    loc = data["location"]
    quat = data["rotation_quat"]
    scl = data["scale"]

    # --- Create and configure the new lattice ---
    active_obj = bpy.context.view_layer.objects.active
    selected_objs = bpy.context.selected_objects[:]

    bpy.ops.object.add(type='LATTICE')
    obj = bpy.context.object

    lt = obj.data
    lt.points_u, lt.points_v, lt.points_w = U, V, W
    interp = data["interp"]
    lt.interpolation_type_u = _decode_bytes(interp[0])
    lt.interpolation_type_v = _decode_bytes(interp[1])
    lt.interpolation_type_w = _decode_bytes(interp[2])
    lt.use_outside = bool(_get1("use_outside", int, 1))
=======
        magic=_bstr(MAGIC, 4),
        version=np.array([VERSION], dtype=np.uint16),
        name=_bstr(obj.name, 64),
        U=np.array([U], dtype=np.uint16),
        V=np.array([V], dtype=np.uint16),
        W=np.array([W], dtype=np.uint16),
        interp=np.array([iu, iv, iw], dtype="|S16"),
        location=loc,
        rotation_quat=quat,
        scale=scl,
        use_outside=np.array([int(lt.use_outside)], dtype=np.uint8),
        points_rest=pts_co,
        points_deform=pts_codeform,
    )
    target = os.path.abspath(os.fspath(filepath))
    directory = os.path.dirname(target) or os.getcwd()
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(target)}.",
        suffix=".npz",
        dir=directory,
    )
    os.close(descriptor)
    try:
        (np.savez_compressed if compressed else np.savez)(temporary, **arrays)
        atomic_replace_staged({target: temporary})
    except Exception:
        try:
            os.remove(temporary)
        except OSError:
            debug_exception(_LOG, "Could not remove the temporary file %s", temporary)
        raise
    return target


def load_lattice_npz(
    filepath, *, context, name=None, link_to_collection=None, update_view: bool = True
):
    with binary_reader(filepath) as stream, np.load(stream, allow_pickle=False) as data:

        def _get1(key, cast=None, default=None):
            if key not in data.files:
                return default
            arr = data[key]
            val = (
                arr.item()
                if arr.shape == ()
                else (arr[0] if arr.ndim == 1 and arr.size == 1 else arr)
            )
            val = _decode_bytes(val)
            return cast(val) if (cast and val is not None) else val

        if _get1("magic") != MAGIC.decode():
            raise ValueError("Not a LATZ lattice file")
        U, V, W = int(_get1("U", int)), int(_get1("V", int)), int(_get1("W", int))
        pts_deform = np.array(data["points_deform"], dtype=np.float32, copy=True)
        loc = np.array(data["location"], dtype=np.float32, copy=True)
        quat = np.array(data["rotation_quat"], dtype=np.float32, copy=True)
        scl = np.array(data["scale"], dtype=np.float32, copy=True)
        interp = tuple(_decode_bytes(value) for value in data["interp"])
        use_outside = bool(_get1("use_outside", int, 1))
        original_name = _get1("name") or "LatticeFromNPZ"

    view_layer = context.view_layer
    active_obj = view_layer.objects.active
    selected_objs = list(context.selected_objects)

    require_finished(bpy.ops.object.add(type="LATTICE"), "Adding the lattice object")
    obj = context.object
    if obj is None or obj.type != "LATTICE":
        raise RuntimeError("Blender did not create the lattice object")

    lt = obj.data
    lt.points_u, lt.points_v, lt.points_w = U, V, W
    lt.interpolation_type_u = interp[0]
    lt.interpolation_type_v = interp[1]
    lt.interpolation_type_w = interp[2]
    lt.use_outside = use_outside
>>>>>>> Stashed changes

    M = Matrix.LocRotScale(Vector(loc), Quaternion(quat), Vector(scl))
    obj.matrix_world = M

<<<<<<< Updated upstream
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
=======
    require_finished(
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True),
        "Applying the lattice transform",
    )
>>>>>>> Stashed changes

    obj.matrix_world = M

    _apply_points(lt, pts_deform, "co_deform")

<<<<<<< Updated upstream
    original_name = _get1("name") or "LatticeFromNPZ"
    obj.name = name if name is not None else original_name
    lt.name = obj.name + "_data"

    coll = link_to_collection or bpy.context.collection
=======
    obj.name = name if name is not None else original_name
    lt.name = obj.name + "_data"

    coll = link_to_collection or context.collection
>>>>>>> Stashed changes
    if obj.name not in coll.objects:
        if obj.users_collection:
            current_coll = obj.users_collection[0]
            current_coll.objects.unlink(obj)
        coll.objects.link(obj)

<<<<<<< Updated upstream
    for o in bpy.context.selected_objects: o.select_set(False)
    for o in selected_objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active_obj

    if update_view:
        bpy.context.view_layer.update()
=======
    for obj_selected in tuple(context.selected_objects):
        obj_selected.select_set(False)
    for obj_selected in selected_objs:
        obj_selected.select_set(True)
    view_layer.objects.active = active_obj

    if update_view:
        view_layer.update()
>>>>>>> Stashed changes

    return obj


<<<<<<< Updated upstream
def add_lattice(target_body_path, collection, fbx_rot, target_body_name):
    """Add lattice from .npz file."""
    lattice_name = f"{target_body_name}Autofitter"
    if lattice_name in collection.objects:
        print(f"{lattice_name} already exists")
        return collection.objects[lattice_name]

    print(f"Creating {lattice_name} from file '{target_body_path}'")
    refitter = load_lattice_npz(target_body_path, name=lattice_name, link_to_collection=collection)
=======
def add_lattice(context, target_body_path, collection, fbx_rot, target_body_name):
    """Add lattice from .npz file"""
    lattice_name = f"{target_body_name}Autofitter"
    if lattice_name in collection.objects:
        _LOG.debug("Lattice already exists: %s", lattice_name)
        return collection.objects[lattice_name]

    _LOG.debug("Creating lattice %s from %s", lattice_name, target_body_path)
    refitter = load_lattice_npz(
        target_body_path,
        context=context,
        name=lattice_name,
        link_to_collection=collection,
    )
>>>>>>> Stashed changes
    refitter["refitter_type"] = target_body_name

    if not fbx_rot:
        refitter.rotation_euler[2] += math.pi

<<<<<<< Updated upstream
    # Hide the lattice
=======
>>>>>>> Stashed changes
    refitter.hide_viewport = True
    return refitter
