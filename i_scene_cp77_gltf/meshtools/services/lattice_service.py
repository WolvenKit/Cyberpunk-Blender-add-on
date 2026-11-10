import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ...assetio.files import binary_reader
from ...blender.operator_results import require_finished
from ...core.log import get_logger

_LOG = get_logger(__name__)

MAGIC = b"LATZ"


def _decode_bytes(val):
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf8", "ignore").rstrip("\x00")
    return val


def _apply_points(lt, pts_f32: np.ndarray, attr: str):
    flat = np.asarray(pts_f32, dtype=np.float32, order="C").reshape(-1)
    lt.points.foreach_set(attr, flat)
    lt.update_tag()


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

    M = Matrix.LocRotScale(Vector(loc), Quaternion(quat), Vector(scl))
    obj.matrix_world = M

    require_finished(
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True),
        "Applying the lattice transform",
    )

    obj.matrix_world = M

    _apply_points(lt, pts_deform, "co_deform")

    obj.name = name if name is not None else original_name
    lt.name = obj.name + "_data"

    coll = link_to_collection or context.collection
    if obj.name not in coll.objects:
        if obj.users_collection:
            current_coll = obj.users_collection[0]
            current_coll.objects.unlink(obj)
        coll.objects.link(obj)

    for obj_selected in tuple(context.selected_objects):
        obj_selected.select_set(False)
    for obj_selected in selected_objs:
        obj_selected.select_set(True)
    view_layer.objects.active = active_obj

    if update_view:
        view_layer.update()

    return obj


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
    refitter["refitter_type"] = target_body_name

    if not fbx_rot:
        refitter.rotation_euler[2] += math.pi

    refitter.hide_viewport = True
    return refitter
