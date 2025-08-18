import bpy
import numpy as np
from ..main.bartmoss_functions import *

MAGIC = b"LATZ"
VERSION = 2
INTERP_VALID = {"KEY_LINEAR", "KEY_CARDINAL", "KEY_BSPLINE", "KEY_CATMULL_ROM"}

def bstr(s, n, enc="utf8"):
    """Pack string/bytes into 1-elem fixed-width bytes array (|S{n}), NUL-padded."""
    if isinstance(s, (bytes, bytearray, np.bytes_)):
        b = bytes(s)
    else:
        b = str(s or "").encode(enc, "ignore")
    b = b[:n].ljust(n, b"\x00")
    return np.array([b], dtype=f"|S{n}")

def points_to_np(lt) -> np.ndarray:
    """(N,3) float32 from lattice points, u-fastest then v then w."""
    n = len(lt.points)
    buf = np.empty(n * 3, dtype=np.float32)
    try:
        lt.points.foreach_get("co_deform", buf)
        return buf.reshape(n, 3)
    except Exception:
        out = np.empty((n, 3), dtype=np.float32)
        for i, p in enumerate(lt.points):
            out[i] = p.co_deform[:]
        return out

def apply_points(lt, pts_f32: np.ndarray):
    """Assign (N,3) float32 to lattice quickly."""
    flat = np.asarray(pts_f32, dtype=np.float32, order="C").reshape(-1)
    try:
        lt.points.foreach_set("co_deform", flat)
    except Exception:
        pts = pts_f32.reshape(-1, 3)
        for i, p in enumerate(lt.points):
            p.co_deform = pts[i]
    if hasattr(lt, "update"): ...
    lt.update_tag()
    bpy.context.view_layer.update()

def rest_grid_flat(U, V, W) -> np.ndarray:
    """Flat (N,3) rest grid (local space), u-fastest then v then w."""
    us = np.linspace(-0.5, 0.5, U, dtype=np.float32)
    vs = np.linspace(-0.5, 0.5, V, dtype=np.float32)
    ws = np.linspace(-0.5, 0.5, W, dtype=np.float32)
    grid = np.stack(np.meshgrid(ws, vs, us, indexing="ij"), axis=-1)  # (W,V,U,3)
    return grid.reshape(-1, 3)

def load_lattice_npz(filepath, *, name=None, link_to_collection=None):
    data = np.load(filepath, allow_pickle=False)

    def _get1(key, cast=None, default=None):
        if key not in data.files:
            return default
        arr = data[key]
        if arr.shape == ():
            val = arr.item()
        elif arr.ndim == 1 and arr.size == 1:
            val = arr[0]
        else:
            val = arr
        if isinstance(val, (bytes, np.bytes_)):
            val = val.decode("utf8", "ignore").rstrip("\x00")
        return cast(val) if cast else val

    if _get1("magic") != MAGIC.decode():
        raise ValueError("Bad magic (not a LATZ lattice)")
    if _get1("version", int) != VERSION:
        raise ValueError("Unsupported version")

    U, V, W = _get1("U", int), _get1("V", int), _get1("W", int)
    N = U * V * W
    if _get1("axis_order") != "u_fastest":
        raise ValueError("Unsupported axis order")

    interp = [s.decode("utf8", "ignore").rstrip("\x00") if isinstance(s, (bytes, np.bytes_)) else str(s)
              for s in data["interp"]]
    iu = interp[0] if interp[0] in INTERP_VALID else "KEY_BSPLINE"
    iv = interp[1] if interp[1] in INTERP_VALID else "KEY_BSPLINE"
    iw = interp[2] if interp[2] in INTERP_VALID else "KEY_BSPLINE"

    pts = np.array(data["points"], copy=False)  # (N,3)
    if pts.shape != (N, 3):
        raise ValueError(f"Points shape mismatch: expected {(N,3)}, got {pts.shape}")

    stored = _get1("stored")
    if stored == "offsets":
        pts = rest_grid_flat(U, V, W) + pts.astype(np.float32, copy=False)
    elif stored == "absolute":
        pts = pts.astype(np.float32, copy=False)
    else:
        raise ValueError(f"Unknown storage mode: {stored!r}")

    # domain reconciliation: if file claims 'half', expand to [-1..1]
    file_domain = _get1("domain", default=None)
    if file_domain is None:
        # heuristic fallback for older bundles - thinking ahead :)
        if float(np.max(np.abs(pts))) <= 0.55:
            pts *= 2.0
    else:
        if file_domain == "half":
            pts *= 2.0

    lt_name = name or _get1("name") or "LatticeFromNPZ"
    lt = bpy.data.lattices.new(lt_name)
    lt.points_u, lt.points_v, lt.points_w = U, V, W
    lt.interpolation_type_u = iu
    lt.interpolation_type_v = iv
    lt.interpolation_type_w = iw
    # restore use_outside if present (default False is typical)
    use_outside = bool(int(_get1("use_outside", int, 1)))
    lt.use_outside = use_outside

    obj = bpy.data.objects.new(lt_name, lt)
    (link_to_collection or bpy.context.collection).objects.link(obj)
    obj.rotation_mode = "QUATERNION"
    obj.location = np.array(data["location"], dtype=np.float32).tolist()
    obj.rotation_quaternion = np.array(data["rotation_quat"], dtype=np.float32).tolist()
    obj.scale = np.array(data["scale"], dtype=np.float32).tolist()

    apply_points(lt, pts)
    return obj

# --- unused: create from raw .npy too --------------------------------
def create_lattice_from_npy(path, *, name="LatticeFromNPY", U=None, V=None, W=None,
                            interp_u="KEY_BSPLINE", interp_v="KEY_BSPLINE", interp_w="KEY_BSPLINE",
                            link_to_collection=None):
    arr = np.load(path, allow_pickle=False)
    if arr.ndim == 4 and arr.shape[-1] == 3:
        W_, V_, U_, _ = arr.shape
        W, V, U = int(W_), int(V_), int(U_)
        pts = arr.reshape(-1, 3)
    elif arr.ndim == 2 and arr.shape[1] == 3:
        assert U and V and W, "Provide U,V,W for flat (N,3) arrays."
        assert U*V*W == arr.shape[0], f"U*V*W={U*V*W} != N={arr.shape[0]}"
        pts = arr
    else:
        raise ValueError(f"Unsupported .npy shape: {arr.shape}")

    lt = bpy.data.lattices.new(name)
    lt.points_u, lt.points_v, lt.points_w = U, V, W
    lt.interpolation_type_u = interp_u
    lt.interpolation_type_v = interp_v
    lt.interpolation_type_w = interp_w

    obj = bpy.data.objects.new(name, lt)
    (link_to_collection or bpy.context.collection).objects.link(obj)
    obj.rotation_mode = "QUATERNION"

    apply_points(lt, np.asarray(pts, dtype=np.float32))
    return obj

# --- writer: save refitter lattice to versioned .npz ------------------------------
def save_lattice_npz(
    obj,
    filepath,
    *,
    fp16: bool = True,
    store_offsets: bool = False,
    compressed: bool = True,
    space: str = "LOCAL",
):
    if obj is None or obj.type != "LATTICE":
        raise TypeError("save_lattice_npz: obj must be a LATTICE object")
    lt = obj.data
    U, V, W = lt.points_u, lt.points_v, lt.points_w
    N = U * V * W
    if N != len(lt.points):
        raise ValueError(f"Lattice point count mismatch: U*V*W={N}, len(points)={len(lt.points)}")

    pts = points_to_np(lt).astype(np.float32, copy=False)  # (N,3) local space points

    stored = "offsets" if store_offsets else "absolute"
    if store_offsets:
        pts = pts - rest_grid_flat(U, V, W)

    test_pts = pts if stored == "absolute" else (rest_grid_flat(U, V, W) + pts.astype(np.float32, copy=False))
    absmax = float(np.max(np.abs(test_pts)))
    domain = "full" # "half" if absmax <= 0.55 else "full" # TODO: domains ?

    pts *= (U - 1, V - 1, W - 1)

    if fp16:
        pts = pts.astype(np.float16, copy=False)

    iu = lt.interpolation_type_u if lt.interpolation_type_u in INTERP_VALID else "KEY_BSPLINE"
    iv = lt.interpolation_type_v if lt.interpolation_type_v in INTERP_VALID else "KEY_BSPLINE"
    iw = lt.interpolation_type_w if lt.interpolation_type_w in INTERP_VALID else "KEY_BSPLINE"

    # Decompose transform in requested space
    if space.upper() == "WORLD":
        loc_v, rot_q, scl_v = obj.matrix_world.decompose()
        q = rot_q.normalized()
        loc  = np.array([loc_v.x, loc_v.y, loc_v.z], dtype=np.float32)
        quat = np.array([q.w, q.x, q.y, q.z], dtype=np.float32)
        scl  = np.array([scl_v.x, scl_v.y, scl_v.z], dtype=np.float32)
    else:
        if obj.rotation_mode == 'QUATERNION':
            q = obj.rotation_quaternion
        else:
            q = obj.rotation_euler.to_quaternion()
        q = q.normalized()
        loc  = np.array(obj.location, dtype=np.float32)
        quat = np.array([q.w, q.x, q.y, q.z], dtype=np.float32)
        scl  = np.array(obj.scale, dtype=np.float32)

    arrays = dict(
        magic=bstr(MAGIC, 4),
        version=np.array([VERSION], dtype=np.uint16),
        name=bstr(obj.name, 64),
        U=np.array([U], dtype=np.uint16),
        V=np.array([V], dtype=np.uint16),
        W=np.array([W], dtype=np.uint16),
        axis_order=bstr("u_fastest", 16),
        space=bstr(space.upper(), 8),
        interp=np.array([iu, iv, iw], dtype="|S16"),
        location=loc,
        rotation_quat=quat,
        scale=scl,
        points=pts,
        points_dtype=bstr("f2" if fp16 else "f4", 2),
        stored=bstr(stored, 8),
        use_outside=np.array([int(lt.use_outside)], dtype=np.uint8),
        domain=bstr(domain, 8),  # 'half' or 'full'
    )
    saver = np.savez_compressed if compressed else np.savez
    saver(filepath, **arrays)
    return filepath
