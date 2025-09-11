import bpy
import numpy as np
from mathutils import Matrix, Vector, Quaternion

MAGIC = b"LATZ"
VERSION = 3
INTERP_VALID = {"KEY_LINEAR", "KEY_CARDINAL", "KEY_BSPLINE", "KEY_CATMULL_ROM"}

# Helpers

def _bstr(s, n, enc="utf8"):
    if isinstance(s, (bytes, bytearray, np.bytes_)): b = bytes(s)
    else: b = str(s or "").encode(enc, "ignore")
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
    if q.w < 0.0: q.negate()
    return q

# Export

def save_lattice_npz(obj, filepath, *, compressed: bool = True):
    if obj is None or obj.type != "LATTICE":
        raise TypeError("save_lattice_npz: obj must be a LATTICE object")

    lt = obj.data
    U, V, W = int(lt.points_u), int(lt.points_v), int(lt.points_w)
    
    # Read rest and deform points from the lattice
    pts_co = _points_to_np(lt, "co")
    pts_codeform = _points_to_np(lt, "co_deform")

    # Decompose world transform
    loc_v, rot_q, scl_v = obj.matrix_world.decompose()
    q = _normalize_quaternion(rot_q)
    loc = np.array(loc_v[:], dtype=np.float32)
    quat = np.array([q.w, q.x, q.y, q.z], dtype=np.float32)
    scl = np.array(scl_v[:], dtype=np.float32)
    
    # Other metadata
    iu = lt.interpolation_type_u
    iv = lt.interpolation_type_v
    iw = lt.interpolation_type_w

    arrays = dict(
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

    M = Matrix.LocRotScale(Vector(loc), Quaternion(quat), Vector(scl))
    obj.matrix_world = M

    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    obj.matrix_world = M

    _apply_points(lt, pts_deform, "co_deform")

    original_name = _get1("name") or "LatticeFromNPZ"
    obj.name = name if name is not None else original_name
    lt.name = obj.name + "_data"
    
    coll = link_to_collection or bpy.context.collection
    if obj.name not in coll.objects:
        if obj.users_collection:
            current_coll = obj.users_collection[0]
            current_coll.objects.unlink(obj)
        coll.objects.link(obj)

    for o in bpy.context.selected_objects: o.select_set(False)
    for o in selected_objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active_obj

    if update_view:
        bpy.context.view_layer.update()

    return obj